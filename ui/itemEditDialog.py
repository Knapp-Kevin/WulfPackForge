from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QCheckBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
)

from data.durability import max_durability
from data.items import CATALOG_GAME_VERSION, completion_labels, resolve_item
from ui.glyphs import item_pixmap


REMOVE_ITEM = 2  # dialog result meaning "take this item out of the inventory"


def _spin(value: int, floor: int, cap: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(min(floor, value), max(cap, value))
    spin.setValue(value)
    return spin


class ItemEditDialog(QDialog):
    """Edit an inventory item with catalog help while preserving modded values."""

    REMOVE = REMOVE_ITEM

    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Inventory Item")
        self.item_data = item_data
        self._build_prefab_input(item_data)
        self._build_value_inputs(item_data)
        self._layout_rows()
        self._apply_catalog_constraints(preserve_existing=True)
        self.quality_input.valueChanged.connect(self._refresh_durability_mode)
        self._refresh_durability_mode()

    # ------------------------------------------------------------ construction
    def _build_prefab_input(self, item_data):
        self.prefab_input = QLineEdit(item_data.get("prefab", ""))
        self.prefab_input.setPlaceholderText("Search by item name or enter a raw/modded prefab ID")
        self.completer = QCompleter(completion_labels(), self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated[str].connect(self._completion_selected)
        self.prefab_input.setCompleter(self.completer)
        self.prefab_input.editingFinished.connect(lambda: self._apply_catalog_constraints(preserve_existing=True))
        self.catalog_status = QLabel()
        self.catalog_status.setWordWrap(True)
        self.glyph_preview = QLabel()
        self.glyph_preview.setFixedSize(80, 80)
        self.glyph_preview.setAlignment(Qt.AlignCenter)
        self.glyph_preview.setAccessibleName("Inventory item preview")

    def _build_value_inputs(self, item_data):
        self.stack_input = _spin(int(item_data.get("stack", 1)), 0, 9999)
        self.quality_input = _spin(int(item_data.get("quality", 1)), 0, 99)
        self.variant_input = _spin(int(item_data.get("variant", 0)), 0, 999)
        self.equipped_input = QCheckBox()
        self.equipped_input.setChecked(item_data.get("equipped", False))

        self._original_durability = item_data.get("durability", 100.0)
        self.durability_input = QDoubleSpinBox()
        self.durability_input.setDecimals(2)
        self.durability_input.setRange(0.0, max(99999.0, float(self._original_durability)))
        self.durability_input.setValue(self._original_durability)
        self.durability_percent = QDoubleSpinBox()
        self.durability_percent.setDecimals(1)
        self.durability_percent.setRange(0.0, 1000.0)  # saves can hold more than the maximum
        self.durability_percent.setSuffix(" %")
        self.durability_label = QLabel("Durability:")
        self._durability_max = None
        self._baseline_percent = None
        self._baseline_quality = int(item_data.get("quality", 1))

    def _layout_rows(self):
        layout = QFormLayout(self)
        layout.addRow("Item / Prefab:", self.prefab_input)
        layout.addRow("Preview:", self.glyph_preview)
        layout.addRow("Catalog:", self.catalog_status)
        layout.addRow("Stack Size:", self.stack_input)
        durability_row = QHBoxLayout()
        durability_row.addWidget(self.durability_percent)
        durability_row.addWidget(self.durability_input)
        layout.addRow(self.durability_label, durability_row)
        layout.addRow("Quality Level:", self.quality_input)
        self.variant_label = QLabel("Variant (Style):")
        layout.addRow(self.variant_label, self.variant_input)
        layout.addRow("Equipped:", self.equipped_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_remove = buttons.addButton("Remove from Inventory", QDialogButtonBox.DestructiveRole)
        self.btn_remove.clicked.connect(self.remove)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    # ------------------------------------------------------------ durability
    def _refresh_durability_mode(self, *_args):
        """Percent of the real maximum when it is known for this prefab and quality, else the raw value."""
        prefab = self.prefab_input.text().strip()
        maximum = max_durability(prefab, self.quality_input.value())
        self._durability_max = maximum
        known = maximum is not None
        self.durability_percent.setVisible(known)
        self.durability_input.setVisible(not known)
        if not known:
            self.durability_label.setText("Durability:")
            return
        if self._baseline_percent is None:
            self._baseline_percent = round(float(self._original_durability) / maximum * 100.0, 1)
            self.durability_percent.setValue(self._baseline_percent)
        self.durability_label.setText(f"Durability (max {maximum:g} at quality {self.quality_input.value()}):")

    def _durability_value(self):
        if self._durability_max is None:
            return self.durability_input.value()
        percent = self.durability_percent.value()
        untouched = percent == self._baseline_percent and self.quality_input.value() == self._baseline_quality
        return self._original_durability if untouched else round(percent / 100.0 * self._durability_max, 2)

    # ------------------------------------------------------------ catalog constraints
    def _completion_selected(self, label):
        item = resolve_item(label)
        if not item:
            return
        self.prefab_input.setText(item.prefab)
        self._apply_catalog_constraints(preserve_existing=False)
        self._baseline_percent = None
        self._refresh_durability_mode()

    @staticmethod
    def _set_preserving_range(widget, minimum, maximum, preserve_existing):
        current = widget.value()
        if preserve_existing:
            minimum = min(minimum, current)
            maximum = max(maximum, current)
        widget.setRange(minimum, maximum)
        if not preserve_existing:
            widget.setValue(max(minimum, min(current, maximum)))

    def _apply_catalog_constraints(self, preserve_existing=True):
        raw_value = self.prefab_input.text().strip()
        item = resolve_item(raw_value)
        self.glyph_preview.setPixmap(item_pixmap(raw_value, 72))
        version_label = f"Valheim {CATALOG_GAME_VERSION}" if CATALOG_GAME_VERSION else "bundled"
        self._set_variant_visible(item is None or item.variants is None or item.variants > 1)
        if not item:
            self._apply_unknown_item(version_label)
            return

        self.prefab_input.setText(item.prefab)
        warnings, details = [], [item.display_name] + ([item.item_type] if item.item_type else [])
        max_variant = max(0, item.variants - 1) if item.variants is not None else None
        limits = (
            (self.stack_input, "stack", 1, item.max_stack, "stack ≤ {}"),
            (self.quality_input, "quality", 1, item.max_quality, "quality ≤ {}"),
            (self.variant_input, "variant", 0, max_variant, "variants 0-{}"),
        )
        for widget, name, floor, cap, detail in limits:
            if cap is None:
                continue
            if preserve_existing and widget.value() > cap:
                warnings.append(f"existing {name} {widget.value()} exceeds known max {cap} and was preserved")
            self._set_preserving_range(widget, floor, cap, preserve_existing)
            details.append(detail.format(cap))

        status = f"{version_label} catalog: " + ", ".join(details)
        if warnings:
            status += ". Compatibility note: " + "; ".join(warnings) + "."
        self.catalog_status.setText(status)

    def _apply_unknown_item(self, version_label):
        self._set_preserving_range(self.stack_input, 0, max(9999, self.stack_input.value()), True)
        self._set_preserving_range(self.quality_input, 0, max(99, self.quality_input.value()), True)
        self._set_preserving_range(self.variant_input, 0, max(999, self.variant_input.value()), True)
        self.catalog_status.setText(
            f"Not found in the {version_label} catalog. Raw values are preserved; "
            "this may be a modded item or an item from a newer game version."
        )

    def _set_variant_visible(self, visible: bool) -> None:
        """Only items with more than one style (or unknown items) show the variant field."""
        self.variant_input.setVisible(visible)
        self.variant_label.setVisible(visible)

    # ------------------------------------------------------------ results
    def remove(self):
        """Close with ``REMOVE``; the inventory tab performs and confirms the deletion."""
        self.done(self.REMOVE)

    def accept(self):
        raw_value = self.prefab_input.text().strip()
        if not raw_value:
            QMessageBox.warning(self, "Item Required",
                                "Choose a known item or enter a raw/modded prefab ID before saving this slot.")
            return
        item = resolve_item(raw_value)
        if item:
            self.prefab_input.setText(item.prefab)
            self._apply_catalog_constraints(preserve_existing=True)
        super().accept()

    def get_updated_data(self):
        raw_value = self.prefab_input.text().strip()
        item = resolve_item(raw_value)
        return {
            "prefab": item.prefab if item else raw_value,
            "stack": self.stack_input.value(),
            "durability": self._durability_value(),
            "quality": self.quality_input.value(),
            "variant": self.variant_input.value(),
            "equipped": self.equipped_input.isChecked(),
        }
