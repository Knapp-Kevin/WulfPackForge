from PySide6.QtWidgets import (
    QComboBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDoubleSpinBox,
    QHeaderView,
    QLabel,
)

from PySide6.QtCore import Qt

from data.skills import VALHEIM_SKILLS
from ui.lifetime import modal
from subscripts.modOverride import apply_overrides, skill_label
from subscripts.workspace import default_workspace_root
from ui.modScanDialog import ModScanDialog
from ui.fieldTracker import FieldTracker


class SkillsTab(QWidget):
    """Skill rows keep a reference to their payload entry; only edited values are written back."""

    def __init__(self):
        super().__init__()
        self.player_data = None
        self.tracker = FieldTracker()

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_toolbar())
        self.empty_hint = QLabel(
            "This character has no skills yet, which is how the game writes a brand-new character. "
            "Use Add Skill for one skill, or Add All Skills to start every vanilla skill at level 0."
        )
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setVisible(False)
        layout.addWidget(self.empty_hint)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Skill Name", "Level (0-100)", "XP Accumulator"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.btn_max_all.clicked.connect(self.maximize_all_skills)
        self.btn_set_all0.clicked.connect(self.set_all_skills0)
        self.btn_add_skill.clicked.connect(self.add_skill)
        self.btn_add_all_skills.clicked.connect(self.add_all_skills)

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        self.btn_max_all = QPushButton("Maximize All (Lvl 100)")
        self.btn_set_all0 = QPushButton("Set All to 0")
        toolbar.addWidget(self.btn_max_all)
        toolbar.addWidget(self.btn_set_all0)
        toolbar.addStretch()
        self.add_skill_combo = QComboBox()
        self.add_skill_combo.setMinimumWidth(180)
        self.btn_add_skill = QPushButton("Add Skill")
        self.btn_add_skill.setEnabled(False)
        self.btn_add_all_skills = QPushButton("Add All Skills")
        self.btn_add_all_skills.setEnabled(False)
        toolbar.addWidget(self.add_skill_combo)
        toolbar.addWidget(self.btn_add_skill)
        toolbar.addWidget(self.btn_add_all_skills)
        self.btn_mods = QPushButton("Mods…")
        self.btn_mods.setToolTip("Scan a BepInEx profile so modded skills and items show their names (optional)")
        self.btn_mods.clicked.connect(self.open_mod_scan)
        toolbar.addWidget(self.btn_mods)
        return toolbar

    def open_mod_scan(self):
        with modal(ModScanDialog(self)) as dialog:
            dialog.scanned.connect(self._mods_scanned)
            dialog.exec()
            dialog.shutdown()

    def _mods_scanned(self, _report):
        apply_overrides(default_workspace_root())
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 0)
            index = cell.data(Qt.UserRole)
            skill = self.player_data["skills"][index] if self.player_data else None
            if skill is not None:
                cell.setText(skill_label(skill.get("id", 0)))

    def load_data(self, player_data):
        self.tracker.clear()
        self.player_data = player_data
        self.table.setRowCount(0)
        for index, skill in enumerate(player_data.get("skills", [])):
            self.add_skill_row(index, skill)
        self._refresh_addable_skills()

    def _refresh_addable_skills(self):
        """Offer every vanilla skill the character does not have yet."""
        self.add_skill_combo.clear()
        present = {skill.get("id") for skill in (self.player_data or {}).get("skills", [])}
        missing = sorted(
            ((name, skill_id) for skill_id, name in VALHEIM_SKILLS.items() if skill_id and skill_id not in present),
            key=lambda pair: pair[0].lower(),
        )
        for name, skill_id in missing:
            self.add_skill_combo.addItem(name, skill_id)
        enabled = bool(self.player_data) and bool(missing)
        self.btn_add_skill.setEnabled(enabled)
        self.btn_add_all_skills.setEnabled(enabled)
        self.empty_hint.setVisible(bool(self.player_data) and self.table.rowCount() == 0)

    def add_skill(self):
        """Append the selected missing skill at level 0 so the player can raise it."""
        skill_id = self.add_skill_combo.currentData()
        if not self.player_data or skill_id is None:
            return
        self._append_skill(int(skill_id))
        self._refresh_addable_skills()

    def add_all_skills(self):
        """Append every vanilla skill the character lacks, all at level 0."""
        if not self.player_data:
            return
        for index in range(self.add_skill_combo.count()):
            self._append_skill(int(self.add_skill_combo.itemData(index)))
        self._refresh_addable_skills()

    def _append_skill(self, skill_id: int):
        skills = self.player_data.setdefault("skills", [])
        skill = {"id": skill_id, "level": 0.0, "xp": 0.0}
        skills.append(skill)
        self.add_skill_row(len(skills) - 1, skill)

    def add_skill_row(self, index, skill_data):
        row = self.table.rowCount()
        self.table.insertRow(row)

        skill_id = skill_data.get("id", 0)
        skill_item = QTableWidgetItem(skill_label(skill_id))
        skill_item.setFlags(skill_item.flags() & ~Qt.ItemIsEditable)
        skill_item.setData(Qt.UserRole, index)
        self.table.setItem(row, 0, skill_item)

        level_spin = QDoubleSpinBox()
        level_spin.setRange(0.0, 100.0)
        level_spin.setDecimals(2)
        level_spin.setValue(skill_data.get("level", 1.0))
        self.table.setCellWidget(row, 1, level_spin)

        xp_spin = QDoubleSpinBox()
        xp_spin.setRange(0.0, 999999.0)
        xp_spin.setDecimals(4)
        xp_spin.setValue(skill_data.get("xp", 0.0))
        self.table.setCellWidget(row, 2, xp_spin)

        self.tracker.remember(("level", index), level_spin.value())
        self.tracker.remember(("xp", index), xp_spin.value())

    def maximize_all_skills(self):
        for row in range(self.table.rowCount()):
            self.table.cellWidget(row, 1).setValue(100.0)

    def set_all_skills0(self):
        for row in range(self.table.rowCount()):
            self.table.cellWidget(row, 1).setValue(0.0)

    def save_changes(self):
        if not self.player_data:
            return

        skills = self.player_data.get("skills", [])
        for row in range(self.table.rowCount()):
            index = self.table.item(row, 0).data(Qt.UserRole)
            if index is None or index >= len(skills):
                continue
            level = self.table.cellWidget(row, 1).value()
            xp = self.table.cellWidget(row, 2).value()
            if self.tracker.changed(("level", index), level):
                skills[index]["level"] = level
            if self.tracker.changed(("xp", index), xp):
                skills[index]["xp"] = xp
