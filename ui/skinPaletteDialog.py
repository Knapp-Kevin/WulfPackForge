"""Pick a realistic skin tone: ten swatches from the Monk Skin Tone scale and a small lightness nudge."""
from typing import List, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from data.skinPalette import LIGHTNESS_NUDGE, PALETTE_ATTRIBUTION, nearest_tone, nudged, palette_tints
from ui.appearancePreview import AppearancePreview
from ui.lifetime import modal

SWATCH_SIZE = 44
NUDGE_STEPS = int(round(LIGHTNESS_NUDGE * 100))  # slider steps of one percent of full scale


def _to_qcolor(rgb: Sequence[float]) -> QColor:
    return QColor(*(int(max(0.0, min(1.0, c)) * 255) for c in rgb[:3]))


class SkinPaletteDialog(QDialog):
    """Ten tones, a nudge, and a head preview; ``result_tint`` is the tint the player chose."""

    def __init__(self, current: Sequence[float], hair_rgb: Sequence[float], hair: str, beard: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a Skin Tone")
        self.tints = palette_tints()
        self.tone = nearest_tone(current)
        self._hair_rgb, self._hair, self._beard = list(hair_rgb), hair, beard
        outer = QHBoxLayout(self)
        column = QVBoxLayout()
        outer.addLayout(column, 1)
        column.addWidget(QLabel("Skin tones for vanilla servers: realistic only, lighter or darker within a small range."))
        column.addLayout(self._build_swatches())
        self.nudge = QSlider(Qt.Horizontal)
        self.nudge.setRange(-NUDGE_STEPS, NUDGE_STEPS)
        self.nudge.setValue(0)
        column.addWidget(QLabel("Lightness nudge:"))
        column.addWidget(self.nudge)
        attribution = QLabel(PALETTE_ATTRIBUTION)
        attribution.setWordWrap(True)
        column.addWidget(attribution)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        column.addWidget(self.buttons)
        self.preview = AppearancePreview(size=160)
        outer.addWidget(self.preview, 0, Qt.AlignTop)
        self.nudge.valueChanged.connect(self._refresh)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._refresh()

    def _build_swatches(self) -> QGridLayout:
        grid = QGridLayout()
        self.swatches: List[QPushButton] = []
        for index, tint in enumerate(self.tints, 1):
            button = QPushButton(str(index))
            button.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
            button.setAutoFillBackground(True)
            palette = button.palette()
            palette.setColor(QPalette.Button, _to_qcolor(tint))
            button.setPalette(palette)
            button.setProperty("tone", index)
            button.clicked.connect(self._swatch_clicked)
            grid.addWidget(button, (index - 1) // 5, (index - 1) % 5)
            self.swatches.append(button)
        return grid

    def _swatch_clicked(self, _checked=False):
        self.tone = int(self.sender().property("tone"))
        self._refresh()

    def result_tint(self) -> List[float]:
        return list(nudged(self.tints[self.tone - 1], self.nudge.value() / 100.0))

    def _refresh(self, *_args):
        for button in self.swatches:
            button.setDown(int(button.property("tone")) == self.tone)
        self.preview.update_preview(self._hair, self._beard, self.result_tint(), self._hair_rgb, 0)

    @staticmethod
    def pick(parent, current: Sequence[float], hair_rgb: Sequence[float] = (0.3, 0.2, 0.1),
             hair: str = "Hair7", beard: str = "BeardNone") -> Optional[List[float]]:
        """Open the dialog on ``current``'s nearest tone; the chosen tint, or ``None`` on cancel."""
        with modal(SkinPaletteDialog(current, hair_rgb, hair, beard, parent)) as dialog:
            return dialog.result_tint() if dialog.exec() == QDialog.Accepted else None
