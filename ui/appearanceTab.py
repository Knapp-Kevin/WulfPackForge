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
)
from PySide6.QtCore import QSize
from data.appearance import BEARD_NONE, HAIR_NONE, VALHEIM_BEARDS, VALHEIM_HAIRS, display_key
from ui.fieldTracker import FieldTracker, select_or_add_unknown
from ui.appearancePreview import AppearancePreview, ColorSwatch
from ui.glyphs import populate_appearance_combo
from ui.hdrColorControls import (
    EXTREME_HDR_THRESHOLD,
    MAX_HDR_COMPONENT,
    HdrColorControls,
    intensity as _intensity,
    picked_rgb as _picked,
    sanitise_loaded_color,
    scaled_from_base as _scaled_from_base,
    sdr_base as _sdr_base,
    to_sdr_qcolor as _to_qcolor,
)

COMBO_ICON = QSize(72, 72)
__all__ = ["AppearanceTab", "EXTREME_HDR_THRESHOLD", "MAX_HDR_COMPONENT"]


class AppearanceTab(QWidget):
    """Appearance controls; unknown styles are shown as raw entries and never replaced."""

    def __init__(self):
        super().__init__()
        self.player_data = None
        self.tracker = FieldTracker()
        self.current_skin_rgb = [1.0, 1.0, 1.0]
        self.current_hair_rgb = [1.0, 1.0, 1.0]
        self._sdr_skin = [1.0, 1.0, 1.0]
        self._sdr_hair = [1.0, 1.0, 1.0]

        outer = QHBoxLayout(self)
        main_layout = QVBoxLayout()
        outer.addLayout(main_layout, 1)
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = AppearancePreview()
        preview_layout.addWidget(self.preview)
        preview_layout.addStretch()
        outer.addWidget(preview_group, 0)

        main_layout.addWidget(self._build_style_group())
        main_layout.addWidget(self._build_color_group())
        self.hdr = HdrColorControls()
        self._alias_hdr_children()
        main_layout.addWidget(self.hdr)
        main_layout.addStretch()
        self._connect()
        self._update_hdr_enabled(False)
        self.refresh_preview()

    # ------------------------------------------------------------ construction
    def _build_style_group(self) -> QGroupBox:
        group = QGroupBox("Physical Customization")
        layout = QFormLayout(group)
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
        return group

    def _build_color_group(self) -> QGroupBox:
        group = QGroupBox("Color Customization")
        layout = QHBoxLayout(group)
        skin_column, self.skin_preview, self.skin_intensity_label, self.btn_skin_color = self._swatch_column(
            "Skin Tone:", "Pick Skin Color"
        )
        hair_column, self.hair_preview, self.hair_intensity_label, self.btn_hair_color = self._swatch_column(
            "Hair/Beard Color:", "Pick Hair Color"
        )
        layout.addLayout(skin_column)
        layout.addSpacing(40)
        layout.addLayout(hair_column)
        return group

    @staticmethod
    def _swatch_column(title: str, button_text: str):
        column = QVBoxLayout()
        column.addWidget(QLabel(title))
        swatch = ColorSwatch()
        label = QLabel("Standard")
        button = QPushButton(button_text)
        column.addWidget(swatch)
        column.addWidget(label)
        column.addWidget(button)
        return column, swatch, label, button

    def _alias_hdr_children(self):
        """Keep the historic attribute names on the tab for callers and tests."""
        self.overbright_checkbox = self.hdr.overbright_checkbox
        self.hdr_help_label = self.hdr.help_label
        self.hdr_controls = self.hdr.controls
        self.skin_hdr_spins = self.hdr.skin_spins
        self.hair_hdr_spins = self.hdr.hair_spins
        self.preset_target_combo = self.hdr.preset_target_combo
        self.hdr_warning_label = self.hdr.warning_label
        buttons = self.hdr.preset_buttons
        self.btn_preset_normal, self.btn_preset_bright = buttons[1.0], buttons[2.0]
        self.btn_preset_glow, self.btn_preset_extreme = buttons[4.0], buttons[8.0]

    def _connect(self):
        self.btn_skin_color.clicked.connect(self.choose_skin_color)
        self.btn_hair_color.clicked.connect(self.choose_hair_color)
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        self.hair_combo.currentIndexChanged.connect(self.refresh_preview)
        self.beard_combo.currentIndexChanged.connect(self.refresh_preview)
        self.overbright_checkbox.toggled.connect(self._update_hdr_enabled)
        self.hdr.values_edited.connect(self._on_hdr_value_changed)
        self.hdr.preset_requested.connect(self.apply_intensity_preset)

    # ------------------------------------------------------------ HDR controls
    def _update_hdr_enabled(self, enabled):
        self.hdr.set_overbright(enabled)
        self.btn_skin_color.setVisible(not enabled)
        self.btn_hair_color.setVisible(not enabled)
        self._refresh_hdr_warning()

    def _sync_hdr_spins(self):
        self.hdr.sync(self.current_skin_rgb, self.current_hair_rgb)

    def _on_hdr_value_changed(self):
        self.current_skin_rgb, self.current_hair_rgb = self.hdr.values()
        self._refresh_color_ui()

    def _refresh_color_ui(self):
        self.update_color_preview(self.skin_preview, self.current_skin_rgb)
        self.update_color_preview(self.hair_preview, self.current_hair_rgb)
        self.skin_intensity_label.setText(self._intensity_text(self.current_skin_rgb))
        self.hair_intensity_label.setText(self._intensity_text(self.current_hair_rgb))
        self._refresh_hdr_warning()
        self.refresh_preview()

    @staticmethod
    def _intensity_text(rgb_list):
        peak = _intensity(rgb_list)
        return "Standard" if peak <= 1.0 else f"HDR {peak:.2f}×"

    def _refresh_hdr_warning(self):
        self.hdr.show_warning(max(_intensity(self.current_skin_rgb), _intensity(self.current_hair_rgb)))

    def apply_intensity_preset(self, factor):
        if factor > 1.0 and not self.overbright_checkbox.isChecked():
            return
        target = self.preset_target_combo.currentData()
        if target in ("skin", "both"):
            self.current_skin_rgb = _scaled_from_base(self._sdr_skin, factor)
        if target in ("hair", "both"):
            self.current_hair_rgb = _scaled_from_base(self._sdr_hair, factor)
        self._sync_hdr_spins()
        self._refresh_color_ui()

    # ------------------------------------------------------------ styles and preview
    def on_model_changed(self, index):
        # The female model has no beard in game; the stored value is still preserved.
        self.beard_combo.setEnabled(self.model_combo.currentData() == 0)
        self.refresh_preview()

    def refresh_preview(self, *_args):
        """Redraw the head from the current widget state; never reads or writes player_data."""
        self.preview.update_preview(
            self.hair_combo.currentData(), self.beard_combo.currentData(),
            self.current_skin_rgb, self.current_hair_rgb, self.model_combo.currentData(),
        )

    def load_data(self, player_data):
        self.tracker.clear()
        self.player_data = player_data
        if not self.player_data:
            return
        select_or_add_unknown(self.model_combo, self.player_data.get("model_index", 0))
        select_or_add_unknown(self.hair_combo, display_key(self.player_data.get("hair", ""), HAIR_NONE))
        select_or_add_unknown(self.beard_combo, display_key(self.player_data.get("beard", ""), BEARD_NONE))
        self.beard_combo.setEnabled(self.model_combo.currentData() == 0)

        self.current_skin_rgb = sanitise_loaded_color(self.player_data.get("skin_color", [1.0, 1.0, 1.0]))
        self.current_hair_rgb = sanitise_loaded_color(self.player_data.get("hair_color", [1.0, 1.0, 1.0]))
        self._sdr_skin = _sdr_base(self.current_skin_rgb)
        self._sdr_hair = _sdr_base(self.current_hair_rgb)
        has_existing_overbright = max(_intensity(self.current_skin_rgb), _intensity(self.current_hair_rgb)) > 1.0
        self.overbright_checkbox.setChecked(has_existing_overbright)
        self._sync_hdr_spins()
        self._refresh_color_ui()

        self.tracker.remember("model_index", self.model_combo.currentData())
        self.tracker.remember("hair", self.hair_combo.currentData())
        self.tracker.remember("beard", self.beard_combo.currentData())
        self.tracker.remember("skin_color", list(self.current_skin_rgb))
        self.tracker.remember("hair_color", list(self.current_hair_rgb))

    def update_color_preview(self, widget, rgb_list):
        widget.set_color(rgb_list)

    def choose_skin_color(self):
        color = QColorDialog.getColor(_to_qcolor(self.current_skin_rgb), self, "Select Skin Color")
        if color.isValid():
            self.current_skin_rgb = _picked(color)
            self._sdr_skin = list(self.current_skin_rgb)
            self._sync_hdr_spins()
            self._refresh_color_ui()

    def choose_hair_color(self):
        color = QColorDialog.getColor(_to_qcolor(self.current_hair_rgb), self, "Select Hair/Beard Color")
        if color.isValid():
            self.current_hair_rgb = _picked(color)
            self._sdr_hair = list(self.current_hair_rgb)
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
