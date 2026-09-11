"""Read-only view of what the character file records: creation, worlds, biomes, trophies, recipes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QFormLayout, QGridLayout, QGroupBox, QLabel, QListWidget,
                               QScrollArea, QVBoxLayout, QWidget)

from subscripts.characterSummary import CharacterSummary, summarize

LIST_SECTIONS = (
    ("trophies", "Trophies"),
    ("biomes", "Known biomes"),
    ("worlds", "Known worlds"),
    ("recipes", "Known recipes"),
    ("stations", "Crafting stations"),
    ("materials", "Known materials"),
    ("uniques", "Unique items"),
    ("foods", "Active food"),
    ("cheat_risk", "Achievement risk"),
)
SCALAR_FIELDS = (
    ("created", "Created"),
    ("player_id", "Player ID"),
    ("guardian_power", "Forsaken power"),
    ("world_count", "Worlds visited"),
)
NOTE = "This tab is a record of the character as saved. Nothing here is edited or written back."


class RecordTab(QWidget):
    """Displays a CharacterSummary; has no editable controls and save_changes writes nothing."""

    def __init__(self):
        super().__init__()
        self.player_data = None
        self.root_save = None
        self.values = {}
        self.lists = {}
        self.groups = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        layout = QVBoxLayout(body)
        note = QLabel(NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(self._build_scalars())
        layout.addLayout(self._build_lists())
        layout.addStretch(1)
        scroll.setWidget(body)
        self.load_data(None, None)

    def _build_scalars(self):
        group = QGroupBox("Character")
        form = QFormLayout(group)
        for key, title in SCALAR_FIELDS:
            label = QLabel()
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.values[key] = label
            form.addRow(f"{title}:", label)
        return group

    def _build_lists(self):
        grid = QGridLayout()
        for index, (key, title) in enumerate(LIST_SECTIONS):
            group = QGroupBox(title)
            box = QVBoxLayout(group)
            widget = QListWidget()
            widget.setSelectionMode(QAbstractItemView.NoSelection)
            widget.setFocusPolicy(Qt.NoFocus)
            box.addWidget(widget)
            self.lists[key], self.groups[key] = widget, group
            grid.addWidget(group, index // 2, index % 2)
        return grid

    def load_data(self, player_data, root_save=None):
        self.player_data, self.root_save = player_data, root_save
        self.show_summary(summarize(root_save, player_data) if player_data else CharacterSummary())

    def show_summary(self, summary: CharacterSummary):
        for key, _title in SCALAR_FIELDS:
            self.values[key].setText(str(getattr(summary, key)))
        for key, title in LIST_SECTIONS:
            entries = getattr(summary, key)
            self.lists[key].clear()
            self.lists[key].addItems(entries)
            self.groups[key].setTitle(f"{title} ({len(entries)})")

    def save_changes(self):
        """Read-only: the record view never changes the save."""
        return None
