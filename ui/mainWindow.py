import copy
import os
import shutil
import tempfile

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import *

from ui.inventoryTab import InventoryTab
from ui.skillsTab import SkillsTab
from ui.statsTab import StatsTab
from ui.appearanceTab import AppearanceTab
from ui.miscTab import MiscTab
from ui.saveStatusWidget import SaveStatusWidget
from ui.valheim_detection import ScanState, ValheimScan, scan_valheim, valheim_warning_message
from ui.branding import APP_NAME, APP_SUBTITLE, APP_AUTHOR, APP_WINDOW_TITLE, banner_path

BANNER_MIN_HEIGHT = 90
BANNER_MAX_HEIGHT = 260


def banner_height_for(width: int, source: QSize) -> int:
    """Label height that shows the whole banner at ``width``, clamped to a sensible band."""
    natural = round(width * source.height() / max(1, source.width()))
    return max(BANNER_MIN_HEIGHT, min(BANNER_MAX_HEIGHT, natural))
from ui.newCharacterDialog import NewCharacterDialog

from subscripts.characterDiscovery import discover_character_saves
from subscripts.fchUtil import serialize_save, write_fch_bytes
from subscripts.newCharacter import create_character_file, root_from_spec
from subscripts.saveErrors import SaveFormatError
from subscripts.saveHealth import build_save_health_report
from subscripts.saveSafety import replace_verified_save, verify_fch_round_trip
from subscripts.workspace import (
    SourceChangedError,
    create_workspace_session,
    store_verified_working_copy,
)

from subscripts.playerDataUtil import (
    pack_player_data_hex,
    payload_is_supported,
    unpack_player_data_hex,
)


class MainWindow(QMainWindow):
    def __init__(self, startup_warning: bool = True):
        super().__init__()

        startup_scan = scan_valheim()
        if startup_warning and startup_scan.state == ScanState.RUNNING:
            warning_msg = valheim_warning_message(startup_scan)
            msg = QMessageBox(self)
            msg.setWindowTitle("Valheim Running")
            msg.setText(warning_msg)
            msg.setInformativeText(
                "You can inspect a character while Valheim is open, but saving is blocked until the game is closed."
            )
            msg.setIcon(QMessageBox.Warning)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

        self.root_save = None
        self.opened_root = None
        self.player_data = None
        self.current_fch = None
        self.current_source = "Local file"
        self.current_modified_at = None
        self.current_payload_supported = True
        self.workspace_session = None
        self.discovered_characters = []

        self.setWindowTitle(APP_WINDOW_TITLE)
        self.resize(1200, 940)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        self._brand_pixmap = QPixmap(str(banner_path()))
        self.brand_banner = QLabel()
        self.brand_banner.setObjectName("brandBanner")
        self.brand_banner.setFixedHeight(banner_height_for(900, self._brand_pixmap.size()))
        self.brand_banner.setAlignment(Qt.AlignCenter)
        self.brand_banner.setAccessibleName(f"{APP_NAME} banner")
        self.brand_banner.setAccessibleDescription(
            f"{APP_NAME}, {APP_SUBTITLE}, by {APP_AUTHOR}."
        )
        self.brand_banner.setStyleSheet(
            "QLabel#brandBanner { background-color: #07151c; border-radius: 8px; }"
        )
        main_layout.addWidget(self.brand_banner)
        self._refresh_brand_banner()

        intro = QLabel(
            "Choose your character, make changes in the tabs below, then click Save Changes. "
            "Wulfpack Forge keeps a protected working copy and backs up the active save before replacement."
        )
        intro.setWordWrap(True)
        main_layout.addWidget(intro)

        discovery_layout = QHBoxLayout()
        self.character_combo = QComboBox()
        self.character_combo.setMinimumWidth(420)
        self.character_combo.setToolTip(
            "Verified Valheim character files found on this computer, including local copies synchronized by Steam Cloud."
        )
        self.btn_refresh_characters = QPushButton("Refresh")
        self.btn_open_discovered = QPushButton("Open Character")
        self.btn_new_character = QPushButton("New Character")
        self.btn_new_character.setToolTip("Create a brand-new character file with the game's starting defaults and open it for editing.")
        discovery_layout.addWidget(QLabel("Character:"))
        discovery_layout.addWidget(self.character_combo, 1)
        discovery_layout.addWidget(self.btn_refresh_characters)
        discovery_layout.addWidget(self.btn_open_discovered)
        discovery_layout.addWidget(self.btn_new_character)
        main_layout.addLayout(discovery_layout)

        self.discovery_help = QLabel()
        self.discovery_help.setWordWrap(True)
        self.discovery_help.setVisible(False)
        main_layout.addWidget(self.discovery_help)

        button_layout = QHBoxLayout()
        self.btn_open_save = QPushButton("Browse for Another Save")
        self.btn_save_save = QPushButton("Save Changes")
        self.btn_save_save.setEnabled(False)
        self.btn_save_save.setToolTip(
            "Verify the edited working copy, confirm the active file has not changed externally, back it up, then apply changes."
        )
        button_layout.addWidget(self.btn_open_save)
        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_save_save)
        main_layout.addLayout(button_layout)

        self.file_label = QLabel("No character loaded")
        main_layout.addWidget(self.file_label)

        self.save_status = SaveStatusWidget()
        main_layout.addWidget(self.save_status)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.inventory_tab = InventoryTab()
        self.skills_tab = SkillsTab()
        self.stats_tab = StatsTab()
        self.appearance_tab = AppearanceTab()
        self.misc_tab = MiscTab()

        self.tabs.addTab(self.appearance_tab, "Appearance")
        self.tabs.addTab(self.inventory_tab, "Inventory")
        self.tabs.addTab(self.skills_tab, "Skills")
        self.tabs.addTab(self.stats_tab, "Stats")
        self.tabs.addTab(self.misc_tab, "Misc")

        self.btn_refresh_characters.clicked.connect(self.refresh_discovered_characters)
        self.btn_open_discovered.clicked.connect(self.open_selected_character)
        self.btn_new_character.clicked.connect(self.create_new_character)
        self.character_combo.activated.connect(lambda _index: self._update_character_tooltip())
        self.btn_open_save.clicked.connect(self.open_save_file)
        self.btn_save_save.clicked.connect(self.save_save_file)

        self.refresh_discovered_characters()

    def _refresh_brand_banner(self):
        if self._brand_pixmap.isNull():
            self.brand_banner.setText(f"{APP_NAME}\n{APP_SUBTITLE}\nby {APP_AUTHOR}")
            return

        width = self.brand_banner.width()
        if width <= 0:
            return
        height = banner_height_for(width, self._brand_pixmap.size())
        self.brand_banner.setFixedHeight(height)
        ratio = self.devicePixelRatioF()
        scaled = self._brand_pixmap.scaled(
            QSize(int(width * ratio), int(height * ratio)),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        self.brand_banner.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "brand_banner"):
            self._refresh_brand_banner()
            QTimer.singleShot(0, self._refresh_brand_banner)  # again once the layout has settled

    def _metadata_for_path(self, filename):
        normalized = os.path.normcase(os.path.abspath(filename))
        for character in self.discovered_characters:
            if os.path.normcase(os.path.abspath(character.path)) == normalized:
                return character.source, character.modified_at

        try:
            modified_at = os.path.getmtime(filename)
        except OSError:
            modified_at = None
        return "Manual file", modified_at

    def _set_health(
        self,
        *,
        valid,
        version,
        source=None,
        modified_at=None,
        error=None,
        backup_path=None,
        source_changed=False,
    ):
        report = build_save_health_report(
            valid=valid,
            version=version,
            source=source or self.current_source,
            modified_at=self.current_modified_at if modified_at is None else modified_at,
            error=error,
            backup_path=backup_path,
            source_changed=source_changed,
            payload_supported=self.current_payload_supported,
        )
        self.save_status.set_report(report)
        self.btn_save_save.setEnabled(bool(self.root_save and self.player_data and report.writable))
        return report

    def refresh_discovered_characters(self):
        previous_path = self.current_fch
        self.discovered_characters = discover_character_saves()
        self.character_combo.clear()

        if not self.discovered_characters:
            self.character_combo.addItem("No local Valheim character files found", None)
            self.btn_open_discovered.setEnabled(False)
            self.character_combo.setToolTip(
                "Wulfpack Forge can only open character files that exist on this computer."
            )
            self.discovery_help.setText(
                "No local character files were found. If this character is stored in Steam Cloud, "
                "make sure Steam has synchronized it to this computer and that Valheim can see it locally, "
                "then click Refresh. Wulfpack Forge does not download saves directly from Steam Cloud. "
                "Use Browse for Another Save if you already have the .fch file elsewhere."
            )
            self.discovery_help.setVisible(True)
            return

        self.discovery_help.setVisible(False)
        selected_index = 0
        for index, character in enumerate(self.discovered_characters):
            self.character_combo.addItem(character.display_label, character.path)
            if previous_path and os.path.normcase(character.path) == os.path.normcase(previous_path):
                selected_index = index

        self.character_combo.setCurrentIndex(selected_index)
        self.btn_open_discovered.setEnabled(True)
        self._update_character_tooltip()

    def _update_character_tooltip(self):
        index = self.character_combo.currentIndex()
        if index < 0 or index >= len(self.discovered_characters):
            return

        character = self.discovered_characters[index]
        details = [
            f"Path: {character.path}",
            f"Source: {character.source}",
            f"Modified: {character.modified_label}",
        ]
        if character.version is not None:
            details.append(f"Save version: {character.version}")
        if character.error:
            details.append(f"Validation: {character.error}")
        else:
            details.append("Validation: checksum and structure verified")
        self.character_combo.setToolTip("\n".join(details))

    def open_selected_character(self):
        filename = self.character_combo.currentData()
        if filename:
            self.load_save_file(filename)

    def create_new_character(self):
        """Create a fresh character file from in-game defaults, then open it."""
        dialog = NewCharacterDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        spec = dialog.result_spec()
        if spec is None:
            return
        try:
            path = create_character_file(spec.directory, root_from_spec(spec))
        except (FileExistsError, SaveFormatError, OSError) as exc:
            QMessageBox.critical(self, "Character Was Not Created", str(exc))
            return
        self.refresh_discovered_characters()
        self.load_save_file(str(path))

    def load_save_file(self, filename):
        source, modified_at = self._metadata_for_path(filename)
        try:
            root_save = verify_fch_round_trip(filename)
            player_hex = root_save.get("player_data_hex")
            if not player_hex:
                self._set_health(
                    valid=False,
                    version=root_save.get("version"),
                    source=source,
                    modified_at=modified_at,
                    error="The save container contains no editable player data.",
                )
                QMessageBox.warning(
                    self,
                    "Character Has No Player Data",
                    "The save container is valid, but it contains no editable player data."
                )
                return

            player_data = unpack_player_data_hex(player_hex)
            workspace_session = create_workspace_session(filename, root_save)

            self.current_payload_supported = payload_is_supported(player_data)
            self.root_save = root_save
            self.opened_root = copy.deepcopy(root_save)
            self.player_data = player_data
            self.current_fch = os.path.abspath(filename)
            self.current_source = source
            self.current_modified_at = modified_at
            self.workspace_session = workspace_session

            self.inventory_tab.load_data(self.player_data)
            self.skills_tab.load_data(self.player_data)
            self.stats_tab.load_data(self.player_data, self.root_save)
            self.appearance_tab.load_data(self.player_data)
            self.misc_tab.load_data(self.player_data, self.root_save)

            self.file_label.setText(
                f"Editing: {self.root_save.get('character_name')}  •  {os.path.basename(filename)}"
            )
            self._set_health(
                valid=True,
                version=self.root_save.get("version"),
                source=source,
                modified_at=modified_at,
            )
            self.tabs.setCurrentWidget(self.appearance_tab)
            self.refresh_discovered_characters()

        except Exception as exc:
            self.root_save = None
            self.opened_root = None
            self.player_data = None
            self.current_fch = None
            self.current_payload_supported = True
            self.workspace_session = None
            self.btn_save_save.setEnabled(False)
            self.file_label.setText("No character loaded")
            self._set_health(
                valid=False,
                version=None,
                source=source,
                modified_at=modified_at,
                error=str(exc),
            )
            QMessageBox.critical(
                self,
                "Character Could Not Be Opened",
                "This save was not loaded because it could not be verified, parsed, and protected safely."
                f"\n\n{str(exc)}"
            )

    def open_save_file(self):
        initial_dir = os.path.dirname(self.current_fch) if self.current_fch else ""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Valheim Character Save",
            initial_dir,
            "Valheim Character (*.fch)"
        )
        if filename:
            self.load_save_file(filename)

    def _block_save_if_valheim_running(self) -> bool:
        scan = scan_valheim()
        if scan.state != ScanState.RUNNING:
            return False

        QMessageBox.critical(
            self,
            "Close Valheim Before Saving",
            f"{valheim_warning_message(scan)}\n\n{APP_NAME} will not write a character save while Valheim is running."
        )
        return True

    def _block_replace_if_valheim_uncertain(self, scan: ValheimScan, working_path: str) -> bool:
        """Only a scan that proves Valheim is closed may touch the active character file."""
        if scan.state == ScanState.NOT_RUNNING:
            return False

        QMessageBox.warning(
            self,
            "Changes kept in your Wulfpack Forge working copy",
            f"{valheim_warning_message(scan)}\n\n"
            f"Your edits were verified and kept in the Wulfpack Forge working copy:\n{working_path}\n\n"
            "The active character file was not replaced. Close Valheim and click Save Changes again to apply them."
        )
        return True

    def _mark_external_change(self, message):
        try:
            modified_at = os.path.getmtime(self.current_fch) if self.current_fch else None
        except OSError:
            modified_at = None
        self.current_modified_at = modified_at
        self._set_health(
            valid=True,
            version=self.root_save.get("version") if self.root_save else None,
            modified_at=modified_at,
            error=message,
            source_changed=True,
        )

    def save_save_file(self):
        """Verify a working copy, guard the active source, back it up, and apply changes."""
        if not self.root_save or not self.player_data or not self.workspace_session or not self.current_fch:
            QMessageBox.warning(self, "No Character Loaded", "Open a character before saving changes.")
            return

        if self._block_save_if_valheim_running():
            return

        session = self.workspace_session
        candidate_path = os.path.join(session.workspace_dir, "working", ".candidate.fch.tmp")
        staged_path = None

        try:
            # Detect Steam, Valheim, another editor, or any other source mutation before doing write work.
            session.assert_source_unchanged()

            self._collect_tab_changes()
            self.root_save["player_data_hex"] = pack_player_data_hex(self.player_data)

            # The candidate is built and verified inside the managed workspace, never in Valheim's save tree.
            write_fch_bytes(serialize_save(self.root_save), candidate_path)
            verify_fch_round_trip(candidate_path, expected_root=self.root_save)
            store_verified_working_copy(candidate_path, session, expected_root=self.root_save)

            if self._block_replace_if_valheim_uncertain(scan_valheim(), session.working_path):
                return

            staged_path = self._stage_candidate(session.working_path)
            backup_path = replace_verified_save(
                staged_path,
                self.current_fch,
                expected_root=self.root_save,
                backup_directory=session.backups_dir,
                expected_destination_sha256=session.expected_source_sha256,
            )
            staged_path = None
            self._finish_apply(backup_path)

        except SourceChangedError as exc:
            self._mark_external_change(str(exc))
            QMessageBox.critical(
                self,
                "Character Changed Outside Wulfpack Forge",
                f"{str(exc)}\n\nYour active character was not replaced. Reload it before applying these edits."
            )
        except Exception as exc:
            if "changed after it was opened" in str(exc) or "disappeared after it was opened" in str(exc):
                self._mark_external_change(str(exc))
            QMessageBox.critical(
                self,
                "Changes Were Not Saved",
                "The active character was not replaced unless every verification and source-consistency check completed successfully."
                f"\n\n{str(exc)}"
            )
        finally:
            for temp_path in (candidate_path, staged_path):
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

    def _collect_tab_changes(self):
        for tab in (self.inventory_tab, self.skills_tab, self.stats_tab, self.appearance_tab, self.misc_tab):
            tab.save_changes()

    def _stage_candidate(self, working_path: str) -> str:
        """Copy the verified working copy next to the destination so the final replace stays atomic."""
        with tempfile.NamedTemporaryFile(
            suffix=".fch",
            prefix=".wulfpack-forge-",
            dir=os.path.dirname(self.current_fch),
            delete=False,
        ) as staged:
            staged_path = staged.name
        shutil.copy2(working_path, staged_path)
        return staged_path

    def _finish_apply(self, backup_path):
        self.workspace_session.update_after_apply(backup_path)
        self.opened_root = copy.deepcopy(self.root_save)

        try:
            self.current_modified_at = os.path.getmtime(self.current_fch)
        except OSError:
            self.current_modified_at = None

        self._set_health(
            valid=True,
            version=self.root_save.get("version"),
            modified_at=self.current_modified_at,
            backup_path=backup_path,
        )

        success_text = f"Changes applied safely to:\n{self.current_fch}"
        if backup_path:
            success_text += f"\n\nPrevious save backed up in the Wulfpack Forge workspace:\n{backup_path}"
        success_text += (
            "\n\nThe working copy passed checksum and round-trip verification, and the active file "
            "was confirmed unchanged before replacement."
        )

        QMessageBox.information(self, "Changes Saved", success_text)
        self.refresh_discovered_characters()
