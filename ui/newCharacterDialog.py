"""Dialog that collects a new character's name, folder, and appearance."""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from data.appearance import BEARD_NONE, HAIR_NONE, VALHEIM_BEARDS, VALHEIM_HAIRS
from subscripts.characterDiscovery import candidate_character_directories
from subscripts.newCharacter import DEFAULT_HAIR_COLOR, DEFAULT_SKIN, NewCharacterSpec, validate_name
from ui.appearancePreview import AppearancePreview
from ui.glyphs import populate_appearance_combo

COMBO_ICON = QSize(72, 72)


def _to_qcolor(rgb) -> QColor:
    return QColor(*(int(max(0.0, min(1.0, c)) * 255) for c in rgb[:3]))


class NewCharacterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Character")
        self.skin_color = list(DEFAULT_SKIN)
        self.hair_color = list(DEFAULT_HAIR_COLOR)

        outer = QHBoxLayout(self)
        layout = QFormLayout()
        outer.addLayout(layout, 1)
        self.preview = AppearancePreview()
        outer.addWidget(self.preview, 0, Qt.AlignTop)
        self._build_identity_rows(layout)
        self._build_appearance_rows(layout)
        layout.addRow(QLabel("The character starts as the game creates it: a torch and a rag tunic, no skills yet."))
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        layout.addRow(self.buttons)
        self._connect()
        self._validate(self.name_input.text())

    def _build_identity_rows(self, layout):
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("3 to 15 letters or digits")
        self.name_error = QLabel()
        self.name_error.setStyleSheet("color: #ee9b96;")
        layout.addRow("Name:", self.name_input)
        layout.addRow("", self.name_error)
        folder_row = QHBoxLayout()
        self.folder_combo = QComboBox()
        self.folder_combo.setEditable(False)
        for path, source in candidate_character_directories():
            self.folder_combo.addItem(f"{source}: {path}", str(path))
        self.btn_browse = QPushButton("Browse")
        folder_row.addWidget(self.folder_combo, 1)
        folder_row.addWidget(self.btn_browse)
        layout.addRow("Save folder:", folder_row)

    def _build_appearance_rows(self, layout):
        self.model_combo = QComboBox()
        self.model_combo.addItem("Male (Model 0)", 0)
        self.model_combo.addItem("Female (Model 1)", 1)
        self.hair_combo = QComboBox()
        self.hair_combo.setIconSize(COMBO_ICON)
        populate_appearance_combo(self.hair_combo, VALHEIM_HAIRS, "hair")
        self.beard_combo = QComboBox()
        self.beard_combo.setIconSize(COMBO_ICON)
        populate_appearance_combo(self.beard_combo, VALHEIM_BEARDS, "beard")
        layout.addRow("Gender Model:", self.model_combo)
        layout.addRow("Hair Style:", self.hair_combo)
        layout.addRow("Beard Style:", self.beard_combo)

        self.skin_preview, self.btn_skin = self._colour_row(layout, "Skin Tone:", self.skin_color)
        self.hair_preview, self.btn_hair = self._colour_row(layout, "Hair/Beard Color:", self.hair_color)

    def _connect(self):
        self.name_input.textChanged.connect(self._validate)
        self.btn_browse.clicked.connect(self._browse)
        self.btn_skin.clicked.connect(lambda: self._pick(self.skin_color, self.skin_preview, "Select Skin Color"))
        self.btn_hair.clicked.connect(lambda: self._pick(self.hair_color, self.hair_preview, "Select Hair Color"))
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        self.hair_combo.currentIndexChanged.connect(self.refresh_preview)
        self.beard_combo.currentIndexChanged.connect(self.refresh_preview)
        self.refresh_preview()
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._validate(self.name_input.text())

    def _colour_row(self, layout, label, rgb):
        row = QHBoxLayout()
        preview = QWidget()
        preview.setFixedSize(60, 24)
        preview.setAutoFillBackground(True)
        self._paint(preview, rgb)
        button = QPushButton("Pick")
        row.addWidget(preview)
        row.addWidget(button)
        row.addStretch()
        layout.addRow(label, row)
        return preview, button

    @staticmethod
    def _paint(widget, rgb):
        palette = widget.palette()
        palette.setColor(QPalette.Window, _to_qcolor(rgb))
        widget.setPalette(palette)

    def _pick(self, target, preview, title):
        color = QColorDialog.getColor(_to_qcolor(target), self, title)
        if color.isValid():
            target[:] = [color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0]
            self._paint(preview, target)
            self.refresh_preview()

    def _model_changed(self, _index):
        self.beard_combo.setEnabled(self.model_combo.currentData() == 0)
        self.refresh_preview()

    def refresh_preview(self, *_args):
        self.preview.update_preview(
            self.hair_combo.currentData(), self.beard_combo.currentData(),
            self.skin_color, self.hair_color, self.model_combo.currentData(),
        )

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Choose the Valheim characters folder")
        if chosen:
            self.folder_combo.addItem(f"Custom: {chosen}", chosen)
            self.folder_combo.setCurrentIndex(self.folder_combo.count() - 1)
            self._validate(self.name_input.text())

    def _validate(self, text: str):
        error = validate_name(text.strip())
        folder = self.folder_combo.currentData()
        if error is None and folder and (Path(folder) / f"{text.strip().lower()}.fch").exists():
            error = "A character with that name already exists in the chosen folder."
        if error is None and not folder:
            error = "Choose a folder for the new character."
        self.name_error.setText(error or "")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(error is None)

    def result_spec(self) -> Optional[NewCharacterSpec]:
        folder = self.folder_combo.currentData()
        if not folder:
            return None
        hair = self.hair_combo.currentData()
        beard = self.beard_combo.currentData()
        return NewCharacterSpec(
            name=self.name_input.text().strip(), directory=str(folder),
            model_index=int(self.model_combo.currentData()),
            hair="" if hair == HAIR_NONE else hair, beard="" if beard == BEARD_NONE else beard,
            skin_color=list(self.skin_color), hair_color=list(self.hair_color),
        )
