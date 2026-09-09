"""Dialog lifetime: the item editor must be released by reference counting, not by the collector.

A dialog caught in a Python reference cycle is destroyed whenever the cyclic collector next runs,
which can be inside an unrelated Qt operation. That is the shape of the native crash this work
follows, so the property is asserted directly rather than inferred from code shape.
"""
import ast
import gc
import json
import os
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shiboken6
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget

import subscripts.variantIcons as vi
import ui.glyphs as glyphs
from subscripts.iconExtraction import INDEX_NAME
from tests.qt_support import QtTestCase
from ui.itemEditDialog import ItemEditDialog
from ui.lifetime import dispose, modal

APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]
PREFAB = "CapeLinen"  # catalog leaves `variants` unset, so the editor does not narrow the spin
STYLE_FILES = [f"{PREFAB}.png", f"{PREFAB}_1.png"]
STYLE_COLOURS = ((200, 30, 30), (30, 60, 200))


def _item(variant=0):
    return {"prefab": PREFAB, "stack": 1, "durability": 100.0, "quality": 1,
            "variant": variant, "equipped": False}


class DialogLifetimeTests(QtTestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        root = Path(self._temp.name)
        cache = root / "icons"
        cache.mkdir(parents=True)
        for name, colour in zip(STYLE_FILES, STYLE_COLOURS):
            image = QImage(8, 8, QImage.Format_ARGB32)
            image.fill(QColor(*colour))
            assert image.save(str(cache / name))
        (cache / INDEX_NAME).write_text(json.dumps({"icons": {PREFAB: STYLE_FILES}}), encoding="utf-8")
        # Both modules import the name, and the environment cannot steer it on macOS.
        self._patches = [patch.object(module, "default_workspace_root", return_value=root)
                         for module in (vi, glyphs)]
        for started in self._patches:
            started.start()
        glyphs.clear_cache()
        self.host = QWidget()

    def tearDown(self):
        for started in self._patches:
            started.stop()
        glyphs.clear_cache()  # the cache is process-global; never leak fixtures into other tests
        self._temp.cleanup()
        super().tearDown()

    def _run_dialog(self, item=None):
        dialog = ItemEditDialog(item or _item(), self.host)
        QTimer.singleShot(0, dialog.reject)
        dialog.exec()
        return dialog

    # ------------------------------------------------------------------ the cycle
    def test_item_edit_dialog_is_not_cyclic_garbage(self):
        gc.disable()
        try:
            refs = []
            for _ in range(12):
                dialog = self._run_dialog()
                refs.append(weakref.ref(dialog))
                del dialog
            alive = [ref for ref in refs if ref() is not None]
        finally:
            gc.enable()
        self.assertEqual(alive, [], f"{len(alive)} of 12 editors waited for the cyclic collector")

    def test_style_sync_holds_no_reference_back_to_the_dialog(self):
        dialog = self._run_dialog()
        held = [value for value in vars(dialog.styles).values()
                if getattr(value, "__self__", None) is dialog]
        self.assertEqual(held, [], "StyleSync holds a bound method of the dialog, closing a cycle")

    # ------------------------------------------------------------------ behaviour kept
    def test_typing_a_variant_still_reaches_the_dialog(self):
        dialog = ItemEditDialog(_item(), self.host)
        before = dialog.glyph_preview.pixmap().toImage()
        dialog.variant_input.setValue(1)
        after = dialog.glyph_preview.pixmap().toImage()
        self.assertNotEqual(before, after, "the preview did not follow the variant")
        self.assertEqual(after.pixelColor(4, 4).getRgb()[:3], STYLE_COLOURS[1])

    def test_choosing_a_style_still_updates_the_number(self):
        dialog = ItemEditDialog(_item(), self.host)
        self.assertEqual(dialog.variant_combo.count(), 2)
        dialog.variant_combo.setCurrentIndex(1)
        self.assertEqual(dialog.variant_input.value(), 1)

    def test_one_variant_change_emits_exactly_once(self):
        dialog = ItemEditDialog(_item(), self.host)
        seen = []
        dialog.styles.changed.connect(seen.append)
        dialog.variant_input.setValue(1)
        self.assertEqual(seen, [1])
        dialog.variant_input.setValue(0)
        self.assertEqual(seen, [1, 0])

    # ------------------------------------------------------------------ disposal
    def test_dispose_destroys_the_dialog_immediately(self):
        gc.disable()
        try:
            dialog = self._run_dialog()
            dispose(dialog)
            self.assertFalse(shiboken6.isValid(dialog))
            self.assertNotIn(dialog, self.host.children())
        finally:
            gc.enable()

    def test_dispose_tolerates_an_already_destroyed_dialog(self):
        dialog = self._run_dialog()
        dispose(dialog)
        self.assertFalse(shiboken6.isValid(dialog), "first dispose did nothing, so the second is vacuous")
        dispose(dialog)

    def test_modal_disposes_on_an_early_return(self):
        captured = {}

        def opens_and_returns():
            with modal(ItemEditDialog(_item(), self.host)) as dialog:
                captured["dialog"] = dialog
                return "left early"

        self.assertEqual(opens_and_returns(), "left early")
        self.assertFalse(shiboken6.isValid(captured["dialog"]))

    def test_modal_disposes_when_the_block_raises(self):
        captured = {}
        with self.assertRaises(ZeroDivisionError):
            with modal(ItemEditDialog(_item(), self.host)) as dialog:
                captured["dialog"] = dialog
                raise ZeroDivisionError("the block failed")
        self.assertFalse(shiboken6.isValid(captured["dialog"]))


class ModalOwnershipRuleTests(unittest.TestCase):
    """Every dialog opened with exec() must be owned by a modal() block.

    Function-granular by construction: it cannot prove a binding is reachable, and it does not
    see attribute receivers or the QMessageBox static helpers. It guards the omission that caused
    this phase rather than proving disposal everywhere.
    """

    EXEMPT = {"QMenu", "QDrag"}  # neither is a dialog, and neither outlives its call

    @staticmethod
    def _constructed(node):
        return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None

    def _offences_in(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offences = []
        for function in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            owned, bound = set(), {}
            for node in ast.walk(function):
                if isinstance(node, ast.withitem) and isinstance(node.optional_vars, ast.Name):
                    call = node.context_expr
                    if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "modal":
                        owned.add(node.optional_vars.id)
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    bound[node.targets[0].id] = self._constructed(node.value)
            for node in ast.walk(function):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "exec" and isinstance(node.func.value, ast.Name)):
                    continue
                name = node.func.value.id
                if name in owned or bound.get(name) in self.EXEMPT:
                    continue
                if name in bound:
                    offences.append(f"{path.name}:{node.lineno} {name}.exec() is not owned by modal()")
        return offences

    def test_every_dialog_exec_site_is_owned_by_modal(self):
        found = [o for path in sorted((ROOT / "ui").glob("*.py")) for o in self._offences_in(path)]
        self.assertEqual(found, [], "\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
