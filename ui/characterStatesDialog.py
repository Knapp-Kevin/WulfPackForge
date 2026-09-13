"""Read-only table of one character's states with Open and Restore actions."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from subscripts.characterRecords import CharacterRecord

COLUMNS = ("State", "Where", "Modified", "Version", "Status")


class CharacterStatesDialog(QDialog):
    open_requested = Signal(str)
    restore_requested = Signal(str, str)  # state path, head path

    def __init__(self, record: CharacterRecord, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(f"States of {record.name}")
        self.resize(900, 420)
        layout = QVBoxLayout(self)
        head = record.head
        layout.addWidget(QLabel(
            f"{record.name}: {len(record.states)} state(s). The active save is "
            f"{head.path if head else 'unknown'}. Restoring a state loads it as a pending edit; "
            "nothing is written until you click Save Changes."
        ))
        self.table = QTableWidget(len(record.states), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, state in enumerate(record.states):
            self._fill_row(row, state)
        layout.addWidget(self.table)
        layout.addLayout(self._build_buttons())
        if record.states:
            self.table.selectRow(0)

    def _fill_row(self, row: int, state) -> None:
        status = "verified" if state.valid else f"needs attention: {state.error}"
        cells = (state.kind_label, f"{state.source}: {state.path}", state.modified_label, str(state.version or "?"), status)
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, state.path)
            item.setToolTip(text)
            self.table.setItem(row, column, item)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.btn_open = QPushButton("Open state")
        self.btn_restore = QPushButton("Restore as active")
        self.btn_restore.setToolTip("Load this state as a pending edit for the active save; apply it with Save Changes.")
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_restore)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        self.btn_open.clicked.connect(self._open)
        self.btn_restore.clicked.connect(self._restore)
        return row

    def selected_path(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.UserRole) if item else None

    def _open(self):
        path = self.selected_path()
        if path:
            self.open_requested.emit(path)
            self.accept()

    def _restore(self):
        path, head = self.selected_path(), self.record.head
        if path and head:
            self.restore_requested.emit(path, head.path)
            self.accept()
