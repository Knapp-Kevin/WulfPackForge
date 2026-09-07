"""Advanced HDR / overbright colour group: opt-in checkbox, RGB rows, presets, and warnings."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

MAX_HDR_COMPONENT = 10.0
EXTREME_HDR_THRESHOLD = 4.0
PRESETS = (("Normal 1×", 1.0), ("Bright 2×", 2.0), ("Glow 4×", 4.0), ("Extreme 8×", 8.0))


def intensity(rgb_list) -> float:
    return max((float(component) for component in rgb_list[:3]), default=0.0)


def to_sdr_qcolor(rgb_list) -> QColor:
    """Map an HDR color to an SDR preview without mutating the stored floats."""
    return QColor(*(int(max(0.0, min(1.0, component)) * 255) for component in rgb_list[:3]))


def picked_rgb(color: QColor) -> list:
    return [color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0]


def sdr_base(rgb_list) -> list:
    """The colour as it would be picked in SDR: unchanged when its peak is at most 1.0, else divided by the peak."""
    safe = [max(0.0, float(component)) for component in rgb_list[:3]]
    peak = max(safe, default=0.0)
    return safe if peak <= 1.0 else [component / peak for component in safe]


def scaled_from_base(base, factor: float) -> list:
    """``factor`` times the SDR base, clamped to the HDR ceiling; 1.0 restores the base exactly."""
    return [min(MAX_HDR_COMPONENT, component * factor) for component in base]


def sanitise_loaded_color(value) -> list:
    """Refuse negative color data while preserving valid overbright values."""
    values = list(value[:3]) if value else [1.0, 1.0, 1.0]
    while len(values) < 3:
        values.append(0.0)
    return [min(MAX_HDR_COMPONENT, max(0.0, float(component))) for component in values]


class HdrColorControls(QGroupBox):
    values_edited = Signal()
    preset_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__("Advanced HDR / Overbright Colors", parent)
        self.syncing = False
        layout = QVBoxLayout(self)
        self.overbright_checkbox = QCheckBox("Allow overbright values above 1.0")
        self.overbright_checkbox.setToolTip(
            "Explicitly enables HDR-style color values above Valheim's normal 0.0–1.0 range. "
            "Negative values are never allowed."
        )
        layout.addWidget(self.overbright_checkbox)
        self.help_label = QLabel(
            "Standard colors use 0.0–1.0. Overbright mode allows up to 10.0 for experimentation. "
            "The swatch and the head preview show hue only; values above 1.0 cannot be represented faithfully on a normal UI."
        )
        self.help_label.setWordWrap(True)
        layout.addWidget(self.help_label)

        # The RGB rows and presets replace the SDR picker buttons while overbright mode is on.
        self.controls = QWidget()
        controls_layout = QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.skin_spins = self._build_row(controls_layout, "Skin RGB:")
        self.hair_spins = self._build_row(controls_layout, "Hair/Beard RGB:")
        self.preset_buttons = self._build_presets_row(controls_layout)
        layout.addWidget(self.controls)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

    def _build_row(self, parent_layout, label):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        spins = []
        for channel in ("R", "G", "B"):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, MAX_HDR_COMPONENT)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setPrefix(f"{channel} ")
            spin.valueChanged.connect(self._spin_changed)
            row.addWidget(spin)
            spins.append(spin)
        row.addStretch()
        parent_layout.addLayout(row)
        return spins

    def _build_presets_row(self, parent_layout):
        row = QHBoxLayout()
        self.preset_target_combo = QComboBox()
        self.preset_target_combo.addItem("Skin", "skin")
        self.preset_target_combo.addItem("Hair/Beard", "hair")
        self.preset_target_combo.addItem("Both", "both")
        row.addWidget(QLabel("Preset target:"))
        row.addWidget(self.preset_target_combo)
        buttons = {}
        for label, factor in PRESETS:
            button = QPushButton(label)
            button.setProperty("factor", factor)
            button.clicked.connect(self._preset_clicked)
            row.addWidget(button)
            buttons[factor] = button
        parent_layout.addLayout(row)
        return buttons

    def _preset_clicked(self, _checked=False):
        self.preset_requested.emit(float(self.sender().property("factor")))

    def _spin_changed(self, _value):
        if not self.syncing:
            self.values_edited.emit()

    def set_overbright(self, enabled: bool):
        self.controls.setVisible(enabled)
        for spin in self.skin_spins + self.hair_spins:
            spin.setEnabled(enabled)
        for factor, button in self.preset_buttons.items():
            button.setEnabled(enabled or factor == 1.0)  # Normal always returns a loaded HDR character to safety

    def sync(self, skin_rgb, hair_rgb):
        self.syncing = True
        try:
            for spin, value in zip(self.skin_spins, skin_rgb):
                spin.setValue(value)
            for spin, value in zip(self.hair_spins, hair_rgb):
                spin.setValue(value)
        finally:
            self.syncing = False

    def values(self):
        return [spin.value() for spin in self.skin_spins], [spin.value() for spin in self.hair_spins]

    def show_warning(self, peak: float):
        if peak > EXTREME_HDR_THRESHOLD:
            self.warning_label.setText(
                f"Extreme overbright value detected ({peak:.2f}). Values above {EXTREME_HDR_THRESHOLD:.1f} "
                "may bloom heavily, wash out the character, or render poorly in Valheim."
            )
        elif peak > 1.0:
            self.warning_label.setText(
                "Overbright values are active. Wulfpack Forge will preserve these floats exactly, but the "
                "visual result depends on Valheim's material/shader behavior."
            )
        else:
            self.warning_label.setText(
                "Safe range active. Negative values are prohibited; enable overbright mode before entering values above 1.0."
            )
