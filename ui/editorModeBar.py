"""The vanilla-friendly appearance mode: its on/off switch, its banner, and what it does to the tabs.

A courtesy for players of vanilla servers such as Jotunheim: with the mode on, skin comes from the
realistic palette, hair and beard colours stay at or below 1.1, the Inventory and Skills tabs are
read-only, and names follow the server's capitalisation rule. It is not enforcement: the mode can
be switched off, and the game file carries no trace of which mode wrote it.
"""
import weakref
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from data.skinPalette import is_palette_tint
from subscripts import workspace
from subscripts.editorMode import HAIR_CAP, MODE_FULL, MODE_VANILLA, load_mode, save_mode
from ui import skinPaletteDialog
from ui.appearanceTab import default_skin_picker

SWITCH_HEIGHT = 44  # a switch a player can read from across the room
SWITCH_ON = "Vanilla-friendly appearance mode: ON"
SWITCH_OFF = "Vanilla-friendly appearance mode: OFF"
SWITCH_STYLE = ("QPushButton { background: #444; color: #ddd; border-radius: 6px; }"
                "QPushButton:checked { background: #2e8b57; color: white; }")
BANNER = ("Vanilla-friendly appearance mode is on: skin from the realistic palette, hair and beard colours up to 1.1, "
          "Inventory and Skills read-only, names with each word capitalised. A courtesy for vanilla servers such as "
          "Jotunheim, not enforcement; switch it off for the full editor.")
PALETTE_REQUIRED = "Choose a skin tone from the palette before saving in vanilla-friendly mode."
HAIR_CAP_REQUIRED = "Hair and beard colours stay at or below 1.1 in vanilla-friendly mode."
HAIR_CAP_TOLERANCE = 1e-6  # 1.1 stored as a float32 reads back as 1.100000023841858


def _palette_picker(parent, current):
    """Resolved when called, so a test may patch the dialog's ``pick`` before or after the toggle."""
    return skinPaletteDialog.SkinPaletteDialog.pick(parent, current)


class EditorModeBar(QWidget):
    mode_changed = Signal(bool)

    def __init__(self, workspace_root=None, parent=None):
        super().__init__(parent)
        self.workspace_root = workspace_root or workspace.default_workspace_root()
        self._window = lambda: None  # a weak reference once applied; a strong one would keep the window alive
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.switch = QPushButton()
        self.switch.setCheckable(True)
        self.switch.setMinimumHeight(SWITCH_HEIGHT)
        self.switch.setFont(QFont(self.switch.font().family(), 12, QFont.Bold))
        self.switch.setStyleSheet(SWITCH_STYLE)
        self.switch.setToolTip("Appearance only, within what a vanilla server expects. Remembered on this computer.")
        self.banner = QLabel(BANNER)
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("color: #e6b450;")
        layout.addWidget(self.switch)
        layout.addWidget(self.banner)
        self.switch.setChecked(load_mode(self.workspace_root) == MODE_VANILLA)
        self._refresh_switch()
        self.banner.setVisible(self.switch.isChecked())
        self.switch.toggled.connect(self._toggled)

    @property
    def vanilla(self) -> bool:
        return self.switch.isChecked()

    def _refresh_switch(self):
        self.switch.setText(SWITCH_ON if self.switch.isChecked() else SWITCH_OFF)

    def _toggled(self, checked: bool):
        save_mode(self.workspace_root, MODE_VANILLA if checked else MODE_FULL)
        self._refresh_switch()
        self.banner.setVisible(checked)
        window = self._window()
        if window is not None:
            self.apply(window)
        self.mode_changed.emit(checked)

    def apply(self, window) -> None:
        """Push the mode into every tab of ``window`` and remember it; called at construction and after every load."""
        self._window = weakref.ref(window)
        on = self.vanilla
        window.inventory_tab.set_read_only(on)
        window.skills_tab.set_read_only(on)
        window.appearance_tab.skin_picker = _palette_picker if on else default_skin_picker
        window.appearance_tab.hdr.set_vanilla_mode(on)
        if on:  # the group is hidden; unchecking overbright brings the Pick buttons back and rewrites no value
            window.appearance_tab.overbright_checkbox.setChecked(False)
        window.misc_tab.set_vanilla_mode(on)

    def blocking_reason(self, window) -> Optional[str]:
        """The one sentence that stops a save in the mode, or ``None`` (always ``None`` off the mode)."""
        if not self.vanilla:
            return None
        if not is_palette_tint(window.appearance_tab.current_skin_rgb):
            return PALETTE_REQUIRED
        if max(window.appearance_tab.current_hair_rgb[:3]) > HAIR_CAP + HAIR_CAP_TOLERANCE:
            return HAIR_CAP_REQUIRED
        return window.misc_tab.name_error()
