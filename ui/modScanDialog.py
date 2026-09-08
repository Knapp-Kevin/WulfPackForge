"""Opt-in dialog: scan a BepInEx plugin set so modded skills and items show their names and icons."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout)

from subscripts.characterDiscovery import registry_steam_path
from subscripts.iconExtraction import find_game_directory
from subscripts.modItems import items_available
from subscripts.modOverride import mods_dir
from subscripts.modProfiles import discover_profiles, profile_from_directory
from subscripts.modScan import scan_profile
from subscripts.workspace import default_workspace_root

POLL_MS = 100
EXPLANATION = (
    "Wulfpack Forge can read the plugin folder of a BepInEx profile so modded skills show their names instead of "
    "numbers and modded items show their names and icons. Plugin files are only read; no mod code runs. The result "
    "is kept in the Wulfpack Forge workspace on this computer. Pick the profile you play the character with."
)
ITEMS_HINT = "Item names and icons need the optional UnityPy package (requirements-optional.txt); skills still scan."


class ModScanDialog(QDialog):
    scanned = Signal(object)  # ScanReport

    def __init__(self, parent=None, profiles=None, out_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Mod Scan")
        self.setMinimumWidth(600)
        self.out_dir = Path(out_dir) if out_dir else mods_dir(default_workspace_root())
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wulfpack-mods")
        self._future = None
        self._lock = Lock()
        self._progress = ("", 0, 0)
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._check)
        self._build(profiles if profiles is not None else discover_profiles(find_game_directory(registry_steam_path())))

    def _build(self, profiles):
        layout = QVBoxLayout(self)
        note = QLabel(EXPLANATION)
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.profiles = QComboBox()
        for profile in profiles:
            self.profiles.addItem(f"{profile.name}  ({profile.plugin_count()} plugins)", profile)
        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.clicked.connect(self._browse)
        row.addWidget(QLabel("Profile:"))
        row.addWidget(self.profiles, 1)
        row.addWidget(self.btn_browse)
        layout.addLayout(row)
        self.status = QLabel("" if items_available() else ITEMS_HINT)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_scan = QPushButton("Scan Profile")
        buttons.addButton(self.btn_scan, QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.reject)
        self.btn_scan.clicked.connect(self.start)
        layout.addWidget(buttons)
        self.btn_scan.setEnabled(self.profiles.count() > 0)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Choose a BepInEx folder (or the folder containing it)")
        profile = profile_from_directory(Path(chosen)) if chosen else None
        if chosen and profile is None:
            self.status.setText("No plugins folder found there. Choose the BepInEx folder of a profile.")
            return
        if profile:
            self.profiles.addItem(f"{profile.name}  ({profile.plugin_count()} plugins)", profile)
            self.profiles.setCurrentIndex(self.profiles.count() - 1)
            self.btn_scan.setEnabled(True)

    def start(self):
        profile = self.profiles.currentData()
        if profile is None:
            return
        self.btn_scan.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status.setText("Starting…")
        self._future = self._executor.submit(scan_profile, profile, self.out_dir, self._report_progress)
        self._poll.start()

    def _report_progress(self, stage, done, total):  # worker thread
        with self._lock:
            self._progress = (stage, done, total)

    def _check(self):
        with self._lock:
            stage, done, total = self._progress
        if stage:
            self.status.setText(f"{stage} ({done}/{total})")
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        if self._future is None or not self._future.done():
            return
        self._poll.stop()
        self._finish()

    def _finish(self):
        future, self._future = self._future, None
        self.btn_scan.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.progress.setRange(0, 1)
        try:
            report = future.result()
        except Exception as exc:
            self.progress.setValue(0)
            self.status.setText(f"Scan failed: {exc}")
            return
        self.progress.setValue(1)
        items = f"{report.item_count} items with {report.icon_count} icons" if report.items_available else "items skipped (UnityPy not installed)"
        self.status.setText(f"Scanned {report.dll_count} plugins in {report.seconds:.0f}s: {report.identifier_count} identifiers, {items}. "
                            f"Saved to {report.catalog_path}.")
        self.scanned.emit(report)

    def shutdown(self) -> None:
        self._poll.stop()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
