from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QLabel,
)

from data.powers import GUARDIAN_POWERS
from ui.fieldTracker import FieldTracker, select_or_add_unknown

MAX_ACTIVE_FOODS = 3
_DEFAULT_VITALS = (("health", 25.0), ("stamina", 50.0))


def _default_vital(key: str) -> float:
    for token, value in _DEFAULT_VITALS:
        if token in key:
            return value
    return 0.0


class StatsTab(QWidget):
    """Vitals, foods, guardian power, and the cheat flag; only edited fields are written back."""

    VITALS = (
        ("max_health", 25.0),
        ("health", 0.0),
        ("max_stamina", 50.0),
        ("stamina", 0.0),
        ("max_eitr", 0.0),
        ("eitr", 0.0),
    )

    def __init__(self):
        super().__init__()
        self.player_data = None
        self.root_save = None
        self.tracker = FieldTracker()
        self.vital_spins = {}

        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._build_vitals_group())
        top_layout.addWidget(self._build_food_group())
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self._build_power_group())
        main_layout.addWidget(self._build_flags_group())
        main_layout.addStretch()
        self.btn_add_food.clicked.connect(self.add_food_from_button)
        self.btn_remove_food.clicked.connect(self.remove_selected_food)

    def _build_vitals_group(self) -> QGroupBox:
        group = QGroupBox("Vitals")
        layout = QFormLayout(group)
        labels = {
            "max_health": "Max Health:", "health": "Current Health:",
            "max_stamina": "Max Stamina:", "stamina": "Current Stamina:",
            "max_eitr": "Max Eitr:", "eitr": "Current Eitr:",
        }
        for key, minimum in self.VITALS:
            spin = QDoubleSpinBox()
            spin.setRange(minimum, 99999.0)
            spin.setValue(max(minimum, _default_vital(key)))
            self.vital_spins[key] = spin
            layout.addRow(labels[key], spin)
        self.max_health_spin = self.vital_spins["max_health"]
        self.health_spin = self.vital_spins["health"]
        self.max_stamina_spin = self.vital_spins["max_stamina"]
        self.stamina_spin = self.vital_spins["stamina"]
        self.max_eitr_spin = self.vital_spins["max_eitr"]
        self.eitr_spin = self.vital_spins["eitr"]
        self.vitals_hint = QLabel(
            "Valheim recalculates maximum health, stamina, and eitr from active food when the character loads, "
            "so an edited maximum is a starting point, not a fixed value. Current values are kept up to that maximum."
        )
        self.vitals_hint.setWordWrap(True)
        self.vitals_hint.setStyleSheet("color: #8fa3ab;")
        layout.addRow(self.vitals_hint)
        return group

    def _build_food_group(self) -> QGroupBox:
        group = QGroupBox(f"Active Food Buffs (Max {MAX_ACTIVE_FOODS})")
        layout = QVBoxLayout(group)
        buttons = QHBoxLayout()
        self.btn_add_food = QPushButton("Add Food")
        self.btn_remove_food = QPushButton("Remove Selected")
        buttons.addWidget(self.btn_add_food)
        buttons.addWidget(self.btn_remove_food)
        layout.addLayout(buttons)
        self.food_table = QTableWidget()
        self.food_table.setColumnCount(2)
        self.food_table.setHorizontalHeaderLabels(["Food Prefab", "Time Left (sec)"])
        self.food_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.food_table)
        return group

    def _build_power_group(self) -> QGroupBox:
        group = QGroupBox("Guardian Power")
        layout = QFormLayout(group)
        self.gp_combo = QComboBox()
        for internal_name, display_name in GUARDIAN_POWERS.items():
            self.gp_combo.addItem(display_name, internal_name)
        self.gp_cooldown_spin = QDoubleSpinBox()
        self.gp_cooldown_spin.setRange(0.0, 999999.0)
        self.gp_cooldown_spin.setSuffix(" seconds")
        layout.addRow("Active Power:", self.gp_combo)
        layout.addRow("Cooldown Remaining:", self.gp_cooldown_spin)
        return group

    def _build_flags_group(self) -> QGroupBox:
        group = QGroupBox("Character Flags")
        layout = QFormLayout(group)
        self.used_cheats_check = QCheckBox("Used Cheats Flag")
        layout.addRow(self.used_cheats_check)
        return group

    def load_data(self, player_data, root_save):
        """Load the nested payload and the outer container; remember what every widget reports."""
        self.tracker.clear()
        self.player_data = player_data
        self.root_save = root_save
        if not self.player_data:
            return

        for key, minimum in self.VITALS:
            spin = self.vital_spins[key]
            loaded = float(self.player_data.get(key, 0.0))
            spin.setRange(min(minimum, loaded), 99999.0)
            spin.setValue(loaded)
            self.tracker.remember(key, spin.value())

        self.food_table.setRowCount(0)
        for food in self.player_data.get("foods", []):
            self.add_food_row(food.get("name", ""), food.get("time", 1200.0))
        self.tracker.remember("foods", self._food_rows())

        select_or_add_unknown(self.gp_combo, self.player_data.get("guardian_power", ""))
        self.tracker.remember("guardian_power", self.gp_combo.currentData())
        self.gp_cooldown_spin.setValue(self.player_data.get("guardian_power_cooldown", 0.0))
        self.tracker.remember("guardian_power_cooldown", self.gp_cooldown_spin.value())

        if self.root_save is not None:
            self.used_cheats_check.setChecked(bool(self.root_save.get("used_cheats", False)))
            self.tracker.remember("used_cheats", self.used_cheats_check.isChecked())

    def add_food_from_button(self):
        if self.food_table.rowCount() < MAX_ACTIVE_FOODS:
            self.add_food_row()

    def add_food_row(self, name="Bread", time=1200.0):
        row = self.food_table.rowCount()
        self.food_table.insertRow(row)
        self.food_table.setItem(row, 0, QTableWidgetItem(name))
        time_spin = QDoubleSpinBox()
        time_spin.setRange(0.0, 99999.0)
        time_spin.setValue(time)
        self.food_table.setCellWidget(row, 1, time_spin)

    def remove_selected_food(self):
        current_row = self.food_table.currentRow()
        if current_row >= 0:
            self.food_table.removeRow(current_row)

    def _food_rows(self):
        rows = []
        for row in range(self.food_table.rowCount()):
            name_item = self.food_table.item(row, 0)
            time_widget = self.food_table.cellWidget(row, 1)
            if name_item and isinstance(time_widget, QDoubleSpinBox):
                rows.append((name_item.text().strip(), time_widget.value()))
        return rows

    def save_changes(self):
        """Write only the fields whose widgets report something different from load time."""
        if not self.player_data:
            return

        for key, _minimum in self.VITALS:
            value = self.vital_spins[key].value()
            if self.tracker.changed(key, value):
                self.player_data[key] = value

        rows = self._food_rows()
        if self.tracker.changed("foods", rows):
            self.player_data["foods"] = [{"name": name, "time": time} for name, time in rows]

        power = self.gp_combo.currentData()
        if self.tracker.changed("guardian_power", power):
            self.player_data["guardian_power"] = power
        cooldown = self.gp_cooldown_spin.value()
        if self.tracker.changed("guardian_power_cooldown", cooldown):
            self.player_data["guardian_power_cooldown"] = cooldown

        cheats = self.used_cheats_check.isChecked()
        if self.root_save is not None and self.tracker.changed("used_cheats", cheats):
            self.root_save["used_cheats"] = cheats
