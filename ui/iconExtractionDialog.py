"""Opt-in dialog: read item icons out of the player's own Valheim install into the workspace."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QVBoxLayout)

from data.items import iter_items
from subscripts.iconExtraction import (INSTALL_HINT, default_game_directory, extract_icons, extraction_available,
                                       icon_cache_dir, is_game_directory)
from subscripts.workspace import default_workspace_root

POLL_MS = 100
EXPLANATION = (
    "Wulfpack Forge can read the item icons from your own Valheim installation and keep copies in its workspace "
    "so inventory tiles show the real icons. The game files are only read. The copies stay on this computer and "
    "are never included in the program, in a save, or in a bug report. Reading the game's bundles takes a minute "
    "or two the first time."
)


class IconExtractionDialog(QDialog):
    """Runs the extraction on a worker thread and reports progress; emits extracted when icons were written."""

    extracted = Signal(object)  # ExtractionReport

    def __init__(self, parent=None, game_dir=None, cache_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Game Icons")
        self.setMinimumWidth(560)
        self.cache_dir = Path(cache_dir) if cache_dir else icon_cache_dir(default_workspace_root())
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wulfpack-icons")
        self._future = None
        self._lock = Lock()
        self._progress = ("", 0, 0)
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._check)
        self._build(game_dir if game_dir is not None else default_game_directory())

    def _build(self, game_dir):
        layout = QVBoxLayout(self)
        note = QLabel(EXPLANATION)
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.game_dir_input = QLineEdit(str(game_dir) if game_dir else "")
        self.game_dir_input.setPlaceholderText("Valheim installation folder (contains valheim_Data)")
        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.clicked.connect(self._browse)
        row.addWidget(QLabel("Game folder:"))
        row.addWidget(self.game_dir_input, 1)
        row.addWidget(self.btn_browse)
        layout.addLayout(row)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_extract = QPushButton("Extract Icons")
        buttons.addButton(self.btn_extract, QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.reject)
        self.btn_extract.clicked.connect(self.start)
        layout.addWidget(buttons)
        if not extraction_available():
            self.status.setText(INSTALL_HINT)
            self.btn_extract.setEnabled(False)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Choose the Valheim installation folder", self.game_dir_input.text())
        if chosen:
            self.game_dir_input.setText(chosen)

    def start(self):
        game_dir = Path(self.game_dir_input.text().strip())
        if not is_game_directory(game_dir):
            self.status.setText("That folder does not contain Valheim's asset bundles (valheim_Data or valheim.app/Contents/Resources/Data, then StreamingAssets/SoftRef/Bundles).")
            return
        prefabs = [item.prefab for item in iter_items()]
        self.btn_extract.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status.setText("Starting…")
        self._future = self._executor.submit(extract_icons, game_dir, prefabs, self.cache_dir, self._report_progress)
        self._poll.start()

    def _report_progress(self, stage, done, total):  # worker thread
        with self._lock:
            self._progress = (stage, done, total)

    def _check(self):
        with self._lock:
            stage, done, total = self._progress
        if stage:
            self.status.setText(f"{stage} ({done}/{total})" if total > 1 else stage)
            self.progress.setRange(0, total if total > 1 else 0)
            self.progress.setValue(done)
        if self._future is None or not self._future.done():
            return
        self._poll.stop()
        self._finish()

    def _finish(self):
        future, self._future = self._future, None
        self.btn_extract.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.progress.setRange(0, 1)
        try:
            report = future.result()
        except Exception as exc:  # the worker logs; show the user why
            self.progress.setValue(0)
            self.status.setText(f"Extraction failed: {exc}")
            return
        self.progress.setValue(1)
        self.status.setText(f"Extracted {report.extracted} of {report.requested} item icons in {report.seconds:.0f}s "
                            f"into {report.cache_dir}. Items without an in-game icon keep the fallback art.")
        self.extracted.emit(report)

    def shutdown(self) -> None:
        self._poll.stop()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
