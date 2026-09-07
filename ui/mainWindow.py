import copy
import logging
import os
import tempfile  # noqa: F401  (patched by the save-flow tests; used through subscripts.saveFlow)

from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)
from ui.inventoryTab import InventoryTab
from ui.skillsTab import SkillsTab
from ui.appearanceTab import AppearanceTab
from ui.miscTab import MiscTab
from ui.saveStatusWidget import SaveStatusWidget
from subscripts.valheim_detection import ScanState, ValheimScan, scan_valheim, valheim_warning_message
from ui.branding import APP_WINDOW_TITLE
from ui.brandBanner import BANNER_MAX_HEIGHT, BANNER_MIN_HEIGHT, BrandBanner, banner_height_for  # noqa: F401
from ui.characterPicker import CharacterPickerBar
from ui.newCharacterDialog import NewCharacterDialog
from subscripts.saveFlow import mtime_or_none, remove_quietly, stage_candidate
from ui import messages
from subscripts.characterRecords import discover_character_records
from subscripts.fchUtil import serialize_save, write_fch_bytes
from subscripts.newCharacter import create_character_file, root_from_spec
from subscripts.saveErrors import SaveFormatError
from subscripts.saveHealth import build_save_health_report
from subscripts.saveSafety import DestinationChangedError, replace_verified_save, verify_fch_round_trip
from subscripts.workspace import SourceChangedError, WorkspaceError, create_workspace_session, store_verified_working_copy
from subscripts.playerDataUtil import pack_player_data_hex, payload_is_supported, unpack_player_data_hex

logger = logging.getLogger(__name__)

_EMPTY_STATE = dict(root_save=None, opened_root=None, player_data=None, current_fch=None, current_source="Local file",
                    current_modified_at=None, current_payload_supported=True, workspace_session=None)


class MainWindow(QMainWindow):
    def __init__(self, startup_warning: bool = True):
        super().__init__()
        if startup_warning:
            self._warn_if_valheim_running()
        self._reset_state()
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.resize(1200, 940)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.brand_banner = BrandBanner()
        self._brand_pixmap = self.brand_banner.source
        layout.addWidget(self.brand_banner)
        self.picker = CharacterPickerBar(discover=lambda: discover_character_records())
        layout.addWidget(self.picker)
        layout.addLayout(self._build_action_row())
        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        self.save_status = SaveStatusWidget()
        layout.addWidget(self.save_status)
        layout.addWidget(self._build_tabs())
        self._set_loaded(False)

        self.picker.open_requested.connect(self.load_save_file)
        self.picker.restore_requested.connect(self.restore_state)
        self.picker.new_requested.connect(self.create_new_character)
        self.refresh_discovered_characters()

    def _warn_if_valheim_running(self):
        scan = scan_valheim()
        if scan.state != ScanState.RUNNING:
            return
        msg = QMessageBox(QMessageBox.Warning, "Valheim Running", valheim_warning_message(scan), QMessageBox.Ok, self)
        msg.setInformativeText(messages.STARTUP_RUNNING_INFO)
        msg.exec()

    def _reset_state(self):
        self.__dict__.update(_EMPTY_STATE)

    def _set_loaded(self, loaded: bool, text: str = ""):
        self.tabs.setEnabled(loaded)
        self.file_label.setText(text if loaded else messages.NO_CHARACTER_LOADED)
        self.file_label.setStyleSheet("" if loaded else "font-weight: 600; color: #e6b450;")

    def _build_action_row(self):
        row = QHBoxLayout()
        self.btn_open_save = QPushButton("Browse for Another Save")
        self.btn_save_save = QPushButton("Save Changes")
        self.btn_save_save.setEnabled(False)
        self.btn_save_save.setToolTip(messages.SAVE_BUTTON_TIP)
        row.addWidget(self.btn_open_save)
        row.addStretch(1)
        row.addWidget(self.btn_save_save)
        self.btn_open_save.clicked.connect(self.open_save_file)
        self.btn_save_save.clicked.connect(self.save_save_file)
        return row

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.inventory_tab, self.skills_tab = InventoryTab(), SkillsTab()
        self.appearance_tab, self.misc_tab = AppearanceTab(), MiscTab()
        for tab, title in ((self.appearance_tab, "Appearance"), (self.inventory_tab, "Inventory"),
                           (self.skills_tab, "Skills"), (self.misc_tab, "Misc")):
            self.tabs.addTab(tab, title)
        return self.tabs

    def refresh_discovered_characters(self):
        self.picker.refresh(self.current_fch)

    def _set_health(self, *, valid, version, source=None, modified_at=None, error=None, backup_path=None, source_changed=False):
        report = build_save_health_report(
            valid=valid, version=version, source=source or self.current_source,
            modified_at=self.current_modified_at if modified_at is None else modified_at,
            error=error, backup_path=backup_path, source_changed=source_changed,
            payload_supported=self.current_payload_supported,
        )
        self.save_status.set_report(report)
        self.btn_save_save.setEnabled(bool(self.root_save and self.player_data and report.writable))
        return report

    def create_new_character(self):
        dialog = NewCharacterDialog(self)
        spec = dialog.result_spec() if dialog.exec() == QDialog.Accepted else None
        if spec is None:
            return
        try:
            path = create_character_file(spec.directory, root_from_spec(spec))
        except (FileExistsError, SaveFormatError, OSError) as exc:
            QMessageBox.critical(self, "Character Was Not Created", str(exc))
            return
        self.refresh_discovered_characters()
        self.load_save_file(str(path))

    def open_save_file(self):
        initial_dir = os.path.dirname(self.current_fch) if self.current_fch else ""
        filename, _ = QFileDialog.getOpenFileName(self, "Open Valheim Character Save", initial_dir, "Valheim Character (*.fch)")
        if filename:
            self.load_save_file(filename)

    def restore_state(self, state_path, head_path):
        self.load_save_file(state_path, apply_to=head_path)

    def load_save_file(self, filename, apply_to=None):
        target = apply_to or filename
        source, modified_at = self.picker.metadata_for(target)
        try:
            root_save = verify_fch_round_trip(filename)
            player_hex = root_save.get("player_data_hex")
            if not player_hex:
                self._set_health(valid=False, version=root_save.get("version"), source=source,
                                 modified_at=modified_at, error=messages.NO_PLAYER_DATA_HEALTH)
                QMessageBox.warning(self, messages.NO_PLAYER_DATA_TITLE, messages.NO_PLAYER_DATA_BODY)
                return
            player_data = unpack_player_data_hex(player_hex)
            session = create_workspace_session(target, root_save)
            self._adopt_loaded(target, root_save, player_data, session, source, modified_at)
            if apply_to:
                self.file_label.setText(messages.restoring(filename, target))
        except Exception as exc:
            logger.exception("Could not open character %s", filename)
            self._reject_load(source, modified_at, exc)

    def _adopt_loaded(self, filename, root_save, player_data, session, source, modified_at):
        self.current_payload_supported = payload_is_supported(player_data)
        self.root_save, self.opened_root = root_save, copy.deepcopy(root_save)
        self.player_data, self.workspace_session = player_data, session
        self.current_fch, self.current_source, self.current_modified_at = os.path.abspath(filename), source, modified_at
        for tab in (self.inventory_tab, self.skills_tab, self.appearance_tab):
            tab.load_data(self.player_data)
        self.misc_tab.load_data(self.player_data, self.root_save)
        self._set_loaded(True, f"Editing: {self.root_save.get('character_name')}  •  {os.path.basename(filename)}")
        self._set_health(valid=True, version=self.root_save.get("version"), source=source, modified_at=modified_at)
        self.tabs.setCurrentWidget(self.appearance_tab)
        self.refresh_discovered_characters()

    def _reject_load(self, source, modified_at, exc):
        self._reset_state()
        self.btn_save_save.setEnabled(False)
        self._set_loaded(False)
        self._set_health(valid=False, version=None, source=source, modified_at=modified_at, error=str(exc))
        QMessageBox.critical(self, "Character Could Not Be Opened", messages.could_not_open(exc))

    def _block_for_valheim(self, scan: ValheimScan, working_path=None) -> bool:
        if scan.state == ScanState.NOT_RUNNING or (working_path is None and scan.state != ScanState.RUNNING):
            return False
        if working_path is None:
            QMessageBox.critical(self, "Close Valheim Before Saving",
                                 messages.close_valheim_before_saving(valheim_warning_message(scan)))
        else:
            QMessageBox.warning(self, "Changes kept in your Wulfpack Forge working copy",
                                messages.kept_in_working_copy(valheim_warning_message(scan), working_path))
        return True

    def _mark_external_change(self, message):
        self.current_modified_at = mtime_or_none(self.current_fch)
        self._set_health(valid=True, version=self.root_save.get("version") if self.root_save else None,
                         modified_at=self.current_modified_at, error=message, source_changed=True)

    def save_save_file(self):
        if not self.root_save or not self.player_data or not self.workspace_session or not self.current_fch:
            QMessageBox.warning(self, "No Character Loaded", "Open a character before saving changes.")
            return
        if self._block_for_valheim(scan_valheim()):
            return
        session = self.workspace_session
        temp_paths = [os.path.join(session.workspace_dir, "working", ".candidate.fch.tmp")]
        try:
            self._apply_changes(session, temp_paths)
        except (SourceChangedError, DestinationChangedError) as exc:
            logger.warning("Save refused: %s", exc)
            self._mark_external_change(str(exc))
            QMessageBox.critical(self, "Character Changed Outside Wulfpack Forge", messages.changed_outside(exc))
        except (WorkspaceError, OSError) as exc:
            logger.exception("Workspace or file error for %s", self.current_fch)
            QMessageBox.critical(self, "Workspace or File Error", messages.not_saved(exc))
        except Exception as exc:
            logger.exception("Save Changes failed for %s", self.current_fch)
            QMessageBox.critical(self, "Changes Were Not Saved", messages.not_saved(exc))
        finally:
            remove_quietly(temp_paths)

    def _apply_changes(self, session, temp_paths):
        """Candidate-first: build and verify inside the workspace, then replace the active file atomically."""
        candidate_path = temp_paths[0]
        session.assert_source_unchanged()  # Steam, Valheim, or another editor may have touched the source
        for tab in (self.inventory_tab, self.skills_tab, self.appearance_tab, self.misc_tab):
            tab.save_changes()
        self.root_save["player_data_hex"] = pack_player_data_hex(self.player_data)
        write_fch_bytes(serialize_save(self.root_save), candidate_path)
        verify_fch_round_trip(candidate_path, expected_root=self.root_save)
        store_verified_working_copy(candidate_path, session, expected_root=self.root_save)
        if self._block_for_valheim(scan_valheim(), session.working_path):
            return
        staged_path = stage_candidate(session.working_path, self.current_fch)
        temp_paths.append(staged_path)
        backup_path = replace_verified_save(
            staged_path, self.current_fch, expected_root=self.root_save,
            backup_directory=session.backups_dir, expected_destination_sha256=session.expected_source_sha256,
        )
        temp_paths.remove(staged_path)  # the replace consumed it
        self._finish_apply(backup_path)

    def _finish_apply(self, backup_path):
        self.workspace_session.update_after_apply(backup_path)
        self.opened_root = copy.deepcopy(self.root_save)
        self.current_modified_at = mtime_or_none(self.current_fch)
        self._set_health(valid=True, version=self.root_save.get("version"), modified_at=self.current_modified_at,
                         backup_path=backup_path)
        QMessageBox.information(self, "Changes Saved", messages.saved_ok(self.current_fch, backup_path))
        self.refresh_discovered_characters()
