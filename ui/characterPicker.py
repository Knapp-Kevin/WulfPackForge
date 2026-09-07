"""Character discovery row: the combo of local saves, Refresh, Open Character, and New Character."""
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

NO_CHARACTERS_HELP = (
    "No local character files were found. If this character is stored in Steam Cloud, "
    "make sure Steam has synchronized it to this computer and that Valheim can see it locally, "
    "then click Refresh. Wulfpack Forge does not download saves directly from Steam Cloud. "
    "Use Browse for Another Save if you already have the .fch file elsewhere."
)


class CharacterPickerBar(QWidget):
    """``discover`` is called on every refresh so the owner controls (and tests can patch) discovery."""

    open_requested = Signal(str)
    new_requested = Signal()

    def __init__(self, discover, parent=None):
        super().__init__(parent)
        self._discover = discover
        self._last_path = None
        self.characters = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        intro = QLabel(
            "Choose your character, make changes in the tabs below, then click Save Changes. "
            "Wulfpack Forge keeps a protected working copy and backs up the active save before replacement."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addLayout(self._build_row())
        self.discovery_help = QLabel()
        self.discovery_help.setWordWrap(True)
        self.discovery_help.setVisible(False)
        layout.addWidget(self.discovery_help)

        self.btn_refresh_characters.clicked.connect(lambda: self.refresh(self._last_path))
        self.btn_open_discovered.clicked.connect(self._emit_open)
        self.btn_new_character.clicked.connect(self.new_requested)
        self.character_combo.activated.connect(lambda _index: self._update_tooltip())

    def _build_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.character_combo = QComboBox()
        self.character_combo.setMinimumWidth(420)
        self.character_combo.setToolTip(
            "Verified Valheim character files found on this computer, including local copies synchronized by Steam Cloud."
        )
        self.btn_refresh_characters = QPushButton("Refresh")
        self.btn_open_discovered = QPushButton("Open Character")
        self.btn_new_character = QPushButton("New Character")
        self.btn_new_character.setToolTip(
            "Create a brand-new character file with the game's starting defaults and open it for editing."
        )
        row.addWidget(QLabel("Character:"))
        row.addWidget(self.character_combo, 1)
        row.addWidget(self.btn_refresh_characters)
        row.addWidget(self.btn_open_discovered)
        row.addWidget(self.btn_new_character)
        return row

    def refresh(self, current_path):
        self._last_path = current_path
        self.characters = self._discover()
        self.character_combo.clear()
        if not self.characters:
            self._show_empty()
            return
        self.discovery_help.setVisible(False)
        selected_index = 0
        for index, character in enumerate(self.characters):
            self.character_combo.addItem(character.display_label, character.path)
            if current_path and os.path.normcase(character.path) == os.path.normcase(current_path):
                selected_index = index
        self.character_combo.setCurrentIndex(selected_index)
        self.btn_open_discovered.setEnabled(True)
        self._update_tooltip()

    def _show_empty(self):
        self.character_combo.addItem("No local Valheim character files found", None)
        self.btn_open_discovered.setEnabled(False)
        self.character_combo.setToolTip("Wulfpack Forge can only open character files that exist on this computer.")
        self.discovery_help.setText(NO_CHARACTERS_HELP)
        self.discovery_help.setVisible(True)

    def metadata_for(self, filename):
        """``(source, modified_at)`` for a path, from discovery when known, else from the filesystem."""
        normalized = os.path.normcase(os.path.abspath(filename))
        for character in self.characters:
            if os.path.normcase(os.path.abspath(character.path)) == normalized:
                return character.source, character.modified_at
        try:
            modified_at = os.path.getmtime(filename)
        except OSError:
            modified_at = None
        return "Manual file", modified_at

    def _update_tooltip(self):
        index = self.character_combo.currentIndex()
        if index < 0 or index >= len(self.characters):
            return
        character = self.characters[index]
        details = [f"Path: {character.path}", f"Source: {character.source}", f"Modified: {character.modified_label}"]
        if character.version is not None:
            details.append(f"Save version: {character.version}")
        details.append(f"Validation: {character.error}" if character.error else "Validation: checksum and structure verified")
        self.character_combo.setToolTip("\n".join(details))

    def _emit_open(self):
        path = self.character_combo.currentData()
        if path:
            self.open_requested.emit(path)
