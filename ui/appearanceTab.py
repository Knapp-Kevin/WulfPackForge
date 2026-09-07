from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QComboBox,
    QPushButton,
    QColorDialog,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QDoubleSpinBox,
)
from PySide6.QtGui import QColor, QPalette
from data.beards import VALHEIM_BEARDS
from data.hairs import VALHEIM_HAIRS
from ui.fieldTracker import FieldTracker, select_or_add_unknown


MAX_HDR_COMPONENT = 10.0
EXTREME_HDR_THRESHOLD = 4.0


def _to_qcolor(rgb_list) -> QColor:
    """Map an HDR color to an SDR preview without mutating the stored floats."""
    return QColor(*(int(max(0.0, min(1.0, component)) * 255) for component in rgb_list[:3]))


def _intensity(rgb_list) -> float:
    return max((float(component) for component in rgb_list[:3]), default=0.0)


def _normalised_with_intensity(rgb_list, intensity: float) -> list[float]:
    """Preserve hue while setting the brightest component to ``intensity``."""
    safe = [max(0.0, float(component)) for component in rgb_list[:3]]
    peak = max(safe, default=0.0)
    if peak <= 0.0:
        return [0.0, 0.0, 0.0]
    scale = intensity / peak
    return [min(MAX_HDR_COMPONENT, component * scale) for component in safe]


class AppearanceTab(QWidget):
    """Appearance controls; unknown styles are shown as raw entries and never replaced."""

    def __init__(self):
        super().__init__()
        self.player_data = None
        self.tracker = FieldTracker()
        self._syncing_hdr = False

        main_layout = QVBoxLayout(self)

        style_group = QGroupBox("Physical Customization")
        style_layout = QFormLayout(style_group)

        self.model_combo = QComboBox()
        self.model_combo.addItem("Male (Model 0)", 0)
        self.model_combo.addItem("Female (Model 1)", 1)

        self.hair_combo = QComboBox()
        for hair_id, hair_name in VALHEIM_HAIRS.items():
            self.hair_combo.addItem(hair_name, hair_id)

        self.beard_combo = QComboBox()
        for beard_id, beard_name in VALHEIM_BEARDS.items():
            self.beard_combo.addItem(beard_name, beard_id)

        style_layout.addRow("Gender Model:", self.model_combo)
        style_layout.addRow("Hair Style:", self.hair_combo)
        style_layout.addRow("Beard Style:", self.beard_combo)
        main_layout.addWidget(style_group)

        color_group = QGroupBox("Color Customization")
        color_layout = QHBoxLayout(color_group)

        skin_vbox = QVBoxLayout()
        skin_vbox.addWidget(QLabel("Skin Tone:"))
        self.btn_skin_color = QPushButton("Pick Skin Color")
        self.skin_preview = QWidget()
        self.skin_preview.setFixedSize(100, 30)
        self.skin_preview.setAutoFillBackground(True)
        self.skin_intensity_label = QLabel("Standard")
        skin_vbox.addWidget(self.skin_preview)
        skin_vbox.addWidget(self.skin_intensity_label)
        skin_vbox.addWidget(self.btn_skin_color)
        color_layout.addLayout(skin_vbox)

        color_layout.addSpacing(40)

        hair_vbox = QVBoxLayout()
        hair_vbox.addWidget(QLabel("Hair/Beard Color:"))
        self.btn_hair_color = QPushButton("Pick Hair Color")
        self.hair_preview = QWidget()
        self.hair_preview.setFixedSize(100, 30)
        self.hair_preview.setAutoFillBackground(True)
        self.hair_intensity_label = QLabel("Standard")
        hair_vbox.addWidget(self.hair_preview)
        hair_vbox.addWidget(self.hair_intensity_label)
        hair_vbox.addWidget(self.btn_hair_color)
        color_layout.addLayout(hair_vbox)

        main_layout.addWidget(color_group)

        hdr_group = QGroupBox("Advanced HDR / Overbright Colors")
        hdr_layout = QVBoxLayout(hdr_group)
        self.overbright_checkbox = QCheckBox("Allow overbright values above 1.0")
        self.overbright_checkbox.setToolTip(
            "Explicitly enables HDR-style color values above Valheim's normal 0.0–1.0 range. "
            "Negative values are never allowed."
        )
        hdr_layout.addWidget(self.overbright_checkbox)

        self.hdr_help_label = QLabel(
            "Standard colors use 0.0–1.0. Overbright mode allows up to 10.0 for experimentation. "
            "The on-screen swatch shows hue only; values above 1.0 cannot be represented faithfully on a normal UI."
        )
        self.hdr_help_label.setWordWrap(True)
        hdr_layout.addWidget(self.hdr_help_label)

        self.skin_hdr_spins = self._build_hdr_row(hdr_layout, "Skin RGB:")
        self.hair_hdr_spins = self._build_hdr_row(hdr_layout, "Hair/Beard RGB:")

        preset_row = QHBoxLayout()
        self.preset_target_combo = QComboBox()
        self.preset_target_combo.addItem("Skin", "skin")
        self.preset_target_combo.addItem("Hair/Beard", "hair")
        self.preset_target_combo.addItem("Both", "both")
        preset_row.addWidget(QLabel("Preset target:"))
        preset_row.addWidget(self.preset_target_combo)

        self.btn_preset_normal = QPushButton("Normal 1×")
        self.btn_preset_bright = QPushButton("Bright 2×")
        self.btn_preset_glow = QPushButton("Glow 4×")
        self.btn_preset_extreme = QPushButton("Extreme 8×")
        for button in (
            self.btn_preset_normal,
            self.btn_preset_bright,
            self.btn_preset_glow,
            self.btn_preset_extreme,
        ):
            preset_row.addWidget(button)
        hdr_layout.addLayout(preset_row)

        self.hdr_warning_label = QLabel()
        self.hdr_warning_label.setWordWrap(True)
        hdr_layout.addWidget(self.hdr_warning_label)
        main_layout.addWidget(hdr_group)
        main_layout.addStretch()

        self.current_skin_rgb = [1.0, 1.0, 1.0]
        self.current_hair_rgb = [1.0, 1.0, 1.0]

        self.btn_skin_color.clicked.connect(self.choose_skin_color)
        self.btn_hair_color.clicked.connect(self.choose_hair_color)
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        self.overbright_checkbox.toggled.connect(self._update_hdr_enabled)

        for spin in self.skin_hdr_spins + self.hair_hdr_spins:
            spin.valueChanged.connect(self._on_hdr_value_changed)

        self.btn_preset_normal.clicked.connect(lambda: self.apply_intensity_preset(1.0))
        self.btn_preset_bright.clicked.connect(lambda: self.apply_intensity_preset(2.0))
        self.btn_preset_glow.clicked.connect(lambda: self.apply_intensity_preset(4.0))
        self.btn_preset_extreme.clicked.connect(lambda: self.apply_intensity_preset(8.0))
        self._update_hdr_enabled(False)

    def _build_hdr_row(self, parent_layout, label_text):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        spins = []
        for channel in ("R", "G", "B"):
            row.addWidget(QLabel(channel))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, MAX_HDR_COMPONENT)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setKeyboardTracking(False)
            spin.setToolTip("0.0 minimum. Negative/underbright values are prohibited.")
            row.addWidget(spin)
            spins.append(spin)
        parent_layout.addLayout(row)
        return spins

    def on_model_changed(self, index):
        # The female model has no beard in game; the stored value is still preserved.
        self.beard_combo.setEnabled(self.model_combo.currentData() == 0)

    def load_data(self, player_data):
        self.tracker.clear()
        self.player_data = player_data
        if not self.player_data:
            return

        select_or_add_unknown(self.model_combo, self.player_data.get("model_index", 0))
        select_or_add_unknown(self.hair_combo, self.player_data.get("hair", "nohair"))
        select_or_add_unknown(self.beard_combo, self.player_data.get("beard", "nobeard"))
        self.beard_combo.setEnabled(self.model_combo.currentData() == 0)

        self.current_skin_rgb = self._sanitise_loaded_color(
            self.player_data.get("skin_color", [1.0, 1.0, 1.0])
        )
        self.current_hair_rgb = self._sanitise_loaded_color(
            self.player_data.get("hair_color", [1.0, 1.0, 1.0])
        )

        has_existing_overbright = max(
            _intensity(self.current_skin_rgb), _intensity(self.current_hair_rgb)
        ) > 1.0
        self.overbright_checkbox.setChecked(has_existing_overbright)
        self._sync_hdr_spins()
        self._refresh_color_ui()

        self.tracker.remember("model_index", self.model_combo.currentData())
        self.tracker.remember("hair", self.hair_combo.currentData())
        self.tracker.remember("beard", self.beard_combo.currentData())
        self.tracker.remember("skin_color", list(self.current_skin_rgb))
        self.tracker.remember("hair_color", list(self.current_hair_rgb))

    def _sanitise_loaded_color(self, value):
        """Refuse negative color data while preserving valid overbright values."""
        values = list(value[:3]) if value else [1.0, 1.0, 1.0]
        while len(values) < 3:
            values.append(0.0)
        return [min(MAX_HDR_COMPONENT, max(0.0, float(component))) for component in values]

    def _update_hdr_enabled(self, enabled):
        for spin in self.skin_hdr_spins + self.hair_hdr_spins:
            spin.setEnabled(enabled)
        for button in (
            self.btn_preset_bright,
            self.btn_preset_glow,
            self.btn_preset_extreme,
        ):
            button.setEnabled(enabled)
        # Normalisation is always available so a loaded HDR character can be returned to the safe range.
        self.btn_preset_normal.setEnabled(True)
        self._refresh_hdr_warning()

    def _sync_hdr_spins(self):
        self._syncing_hdr = True
        try:
            for spin, value in zip(self.skin_hdr_spins, self.current_skin_rgb):
                spin.setValue(value)
            for spin, value in zip(self.hair_hdr_spins, self.current_hair_rgb):
                spin.setValue(value)
        finally:
            self._syncing_hdr = False

    def _on_hdr_value_changed(self, _value):
        if self._syncing_hdr:
            return
        self.current_skin_rgb = [spin.value() for spin in self.skin_hdr_spins]
        self.current_hair_rgb = [spin.value() for spin in self.hair_hdr_spins]
        self._refresh_color_ui()

    def _refresh_color_ui(self):
        self.update_color_preview(self.skin_preview, self.current_skin_rgb)
        self.update_color_preview(self.hair_preview, self.current_hair_rgb)
        self.skin_intensity_label.setText(self._intensity_text(self.current_skin_rgb))
        self.hair_intensity_label.setText(self._intensity_text(self.current_hair_rgb))
        self._refresh_hdr_warning()

    def _intensity_text(self, rgb_list):
        peak = _intensity(rgb_list)
        if peak <= 1.0:
            return "Standard"
        return f"HDR {peak:.2f}×"

    def _refresh_hdr_warning(self):
        peak = max(_intensity(self.current_skin_rgb), _intensity(self.current_hair_rgb))
        if peak > EXTREME_HDR_THRESHOLD:
            self.hdr_warning_label.setText(
                f"Extreme overbright value detected ({peak:.2f}). Values above {EXTREME_HDR_THRESHOLD:.1f} "
                "may bloom heavily, wash out the character, or render poorly in Valheim."
            )
        elif peak > 1.0:
            self.hdr_warning_label.setText(
                "Overbright values are active. Wulfpack Forge will preserve these floats exactly, but the "
                "visual result depends on Valheim's material/shader behavior."
            )
        else:
            self.hdr_warning_label.setText(
                "Safe range active. Negative values are prohibited; enable overbright mode before entering values above 1.0."
            )

    def update_color_preview(self, widget, rgb_list):
        palette = widget.palette()
        palette.setColor(QPalette.Window, _to_qcolor(rgb_list))
        widget.setPalette(palette)

    def choose_skin_color(self):
        color = QColorDialog.getColor(_to_qcolor(self.current_skin_rgb), self, "Select Skin Color")
        if color.isValid():
            self.current_skin_rgb = [color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0]
            self._sync_hdr_spins()
            self._refresh_color_ui()

    def choose_hair_color(self):
        color = QColorDialog.getColor(_to_qcolor(self.current_hair_rgb), self, "Select Hair/Beard Color")
        if color.isValid():
            self.current_hair_rgb = [color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0]
            self._sync_hdr_spins()
            self._refresh_color_ui()

    def apply_intensity_preset(self, intensity):
        if intensity > 1.0 and not self.overbright_checkbox.isChecked():
            return

        target = self.preset_target_combo.currentData()
        if target in ("skin", "both"):
            self.current_skin_rgb = _normalised_with_intensity(self.current_skin_rgb, intensity)
        if target in ("hair", "both"):
            self.current_hair_rgb = _normalised_with_intensity(self.current_hair_rgb, intensity)

        self._sync_hdr_spins()
        self._refresh_color_ui()

    def save_changes(self):
        if not self.player_data:
            return

        pending = {
            "model_index": self.model_combo.currentData(),
            "hair": self.hair_combo.currentData(),
            "beard": self.beard_combo.currentData(),
            "skin_color": list(self.current_skin_rgb),
            "hair_color": list(self.current_hair_rgb),
        }
        for key, value in pending.items():
            if self.tracker.changed(key, value):
                self.player_data[key] = value
