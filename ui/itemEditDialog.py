from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from data.items import CATALOG_GAME_VERSION, completion_labels, resolve_item
from ui.glyphs import item_pixmap


REMOVE_ITEM = 2  # dialog result meaning "take this item out of the inventory"

class ItemEditDialog(QDialog):
    """Edit an inventory item with catalog help while preserving modded values."""

    REMOVE = REMOVE_ITEM

    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Inventory Item")
        self.item_data = item_data

        layout = QFormLayout(self)

        self.prefab_input = QLineEdit(item_data.get("prefab", ""))
        self.prefab_input.setPlaceholderText("Search by item name or enter a raw/modded prefab ID")

        self.completer = QCompleter(completion_labels(), self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated[str].connect(self._completion_selected)
        self.prefab_input.setCompleter(self.completer)
        self.prefab_input.editingFinished.connect(
            lambda: self._apply_catalog_constraints(preserve_existing=True)
        )

        self.catalog_status = QLabel()
        self.catalog_status.setWordWrap(True)

        self.glyph_preview = QLabel()
        self.glyph_preview.setFixedSize(80, 80)
        self.glyph_preview.setAlignment(Qt.AlignCenter)
        self.glyph_preview.setAccessibleName("Inventory item preview")

        stack_value = int(item_data.get("stack", 1))
        quality_value = int(item_data.get("quality", 1))
        variant_value = int(item_data.get("variant", 0))

        self.stack_input = QSpinBox()
        self.stack_input.setRange(min(0, stack_value), max(9999, stack_value))
        self.stack_input.setValue(stack_value)

        self.durability_input = QDoubleSpinBox()
        self.durability_input.setDecimals(2)
        self.durability_input.setRange(0.0, max(99999.0, float(item_data.get("durability", 100.0))))
        self.durability_input.setValue(item_data.get("durability", 100.0))

        self.quality_input = QSpinBox()
        self.quality_input.setRange(min(0, quality_value), max(99, quality_value))
        self.quality_input.setValue(quality_value)

        self.variant_input = QSpinBox()
        self.variant_input.setRange(min(0, variant_value), max(999, variant_value))
        self.variant_input.setValue(variant_value)

        self.equipped_input = QCheckBox()
        self.equipped_input.setChecked(item_data.get("equipped", False))

        layout.addRow("Item / Prefab:", self.prefab_input)
        layout.addRow("Preview:", self.glyph_preview)
        layout.addRow("Catalog:", self.catalog_status)
        layout.addRow("Stack Size:", self.stack_input)
        layout.addRow("Durability:", self.durability_input)
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

        self._apply_catalog_constraints(preserve_existing=True)

    def _completion_selected(self, label):
        item = resolve_item(label)
        if not item:
            return
        self.prefab_input.setText(item.prefab)
        self._apply_catalog_constraints(preserve_existing=False)

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
            self._set_preserving_range(
                self.stack_input, 0, max(9999, self.stack_input.value()), True
            )
            self._set_preserving_range(
                self.quality_input, 0, max(99, self.quality_input.value()), True
            )
            self._set_preserving_range(
                self.variant_input, 0, max(999, self.variant_input.value()), True
            )
            self.catalog_status.setText(
                f"Not found in the {version_label} catalog. Raw values are preserved; "
                "this may be a modded item or an item from a newer game version."
            )
            return

        self.prefab_input.setText(item.prefab)
        warnings = []
        details = [item.display_name]
        if item.item_type:
            details.append(item.item_type)

        if item.max_stack is not None:
            if preserve_existing and self.stack_input.value() > item.max_stack:
                warnings.append(
                    f"existing stack {self.stack_input.value()} exceeds known max {item.max_stack} and was preserved"
                )
            self._set_preserving_range(
                self.stack_input, 1, item.max_stack, preserve_existing
            )
            details.append(f"stack ≤ {item.max_stack}")

        if item.max_quality is not None:
            if preserve_existing and self.quality_input.value() > item.max_quality:
                warnings.append(
                    f"existing quality {self.quality_input.value()} exceeds known max {item.max_quality} and was preserved"
                )
            self._set_preserving_range(
                self.quality_input, 1, item.max_quality, preserve_existing
            )
            details.append(f"quality ≤ {item.max_quality}")

        if item.variants is not None:
            max_variant = max(0, item.variants - 1)
            if preserve_existing and self.variant_input.value() > max_variant:
                warnings.append(
                    f"existing variant {self.variant_input.value()} exceeds known max {max_variant} and was preserved"
                )
            self._set_preserving_range(
                self.variant_input, 0, max_variant, preserve_existing
            )
            details.append(f"variants 0-{max_variant}")

        status = f"{version_label} catalog: " + ", ".join(details)
        if warnings:
            status += ". Compatibility note: " + "; ".join(warnings) + "."
        self.catalog_status.setText(status)

    def _set_variant_visible(self, visible: bool) -> None:
        """Only items with more than one style (or unknown items) show the variant field."""
        self.variant_input.setVisible(visible)
        self.variant_label.setVisible(visible)

    def remove(self):
        """Close with ``REMOVE``; the inventory tab performs and confirms the deletion."""
        self.done(self.REMOVE)

    def accept(self):
        raw_value = self.prefab_input.text().strip()
        if not raw_value:
            QMessageBox.warning(
                self,
                "Item Required",
                "Choose a known item or enter a raw/modded prefab ID before saving this slot."
            )
            return

        item = resolve_item(raw_value)
        if item:
            self.prefab_input.setText(item.prefab)
            self._apply_catalog_constraints(preserve_existing=True)

        super().accept()

    def get_updated_data(self):
        raw_value = self.prefab_input.text().strip()
        item = resolve_item(raw_value)
        prefab = item.prefab if item else raw_value

        return {
            "prefab": prefab,
            "stack": self.stack_input.value(),
            "durability": self.durability_input.value(),
            "quality": self.quality_input.value(),
            "variant": self.variant_input.value(),
            "equipped": self.equipped_input.isChecked(),
        }
