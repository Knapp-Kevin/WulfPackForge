from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit

from subscripts.newCharacter import validate_name
from ui.fieldTracker import FieldTracker


class MiscTab(QWidget):
    """Character identity fields stored on the outer container."""

    def __init__(self):
        super().__init__()
        self.player_data = None
        self.root_save = None
        self.tracker = FieldTracker()
        self.vanilla = False  # the vanilla-friendly appearance mode: an edited name follows the capitalisation rule

        main_layout = QVBoxLayout(self)

        identity_group = QGroupBox("Character Identity")
        identity_layout = QFormLayout(identity_group)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter character name...")

        identity_layout.addRow("Character Name:", self.name_input)
        main_layout.addWidget(identity_group)
        main_layout.addStretch()

    def load_data(self, player_data, root_save=None):
        """The character name lives on the outer container; the payload is not consulted."""
        self.tracker.clear()
        self.player_data = player_data
        self.root_save = root_save

        name = "Viking"
        if self.root_save and "character_name" in self.root_save:
            name = self.root_save["character_name"]
        self.name_input.setText(name)
        self.tracker.remember("character_name", self.name_input.text())

    def set_vanilla_mode(self, vanilla: bool) -> None:
        self.vanilla = vanilla

    def name_error(self):
        """The rule's message for an edited name, or None; a name the player has not touched is never checked."""
        text = self.name_input.text()
        if not self.tracker.changed("character_name", text):
            return None
        return validate_name(text.strip(), capitalised_words=self.vanilla)

    def save_changes(self):
        """Write the name to the outer container only when it was edited and is not blank."""
        new_name = self.name_input.text().strip()
        if not new_name or self.root_save is None:
            return
        if self.tracker.changed("character_name", self.name_input.text()):
            self.root_save["character_name"] = new_name
