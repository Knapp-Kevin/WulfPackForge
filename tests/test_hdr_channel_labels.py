"""The HDR channel letters render beside their value fields, never inside them."""
import os
import unittest

from tests.qt_support import QtTestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLabel

from ui.hdrColorControls import HdrColorControls


APP = QApplication.instance() or QApplication([])

CHANNELS = ("R", "G", "B")


def row_widgets(controls, spin):
    """The widgets of the row holding ``spin``, in layout order (None for the trailing stretch)."""
    layout = controls.controls.layout()
    for index in range(layout.count()):
        row = layout.itemAt(index).layout()
        if row is None:
            continue
        widgets = [row.itemAt(i).widget() for i in range(row.count())]
        if spin in widgets:
            return widgets
    raise AssertionError("the spin box is not in any row of the controls layout")


class HdrChannelLabelTests(QtTestCase):
    def test_no_channel_letter_is_drawn_inside_a_value_field(self):
        controls = HdrColorControls()
        controls.sync([2.0, 1.5, 0.25], [4.0, 0.5, 0.125])
        for spin in controls.skin_spins + controls.hair_spins:
            self.assertEqual(spin.prefix(), "")
            self.assertEqual(spin.suffix(), "")
        self.assertEqual(controls.skin_spins[0].text(), "2.000")
        self.assertEqual(controls.hair_spins[2].text(), "0.125")

    def test_each_letter_is_its_own_label_immediately_before_its_field(self):
        controls = HdrColorControls()
        for spins in (controls.skin_spins, controls.hair_spins):
            for channel, spin in zip(CHANNELS, spins):
                widgets = row_widgets(controls, spin)
                preceding = widgets[widgets.index(spin) - 1]
                self.assertIsInstance(preceding, QLabel)
                self.assertEqual(preceding.text(), channel)
                self.assertIs(preceding.buddy(), spin)

    def test_each_field_announces_its_row_and_channel(self):
        controls = HdrColorControls()
        for row_name, spins in (("Skin RGB", controls.skin_spins),
                                ("Hair/Beard RGB", controls.hair_spins)):
            for channel, spin in zip(CHANNELS, spins):
                self.assertEqual(spin.accessibleName(), f"{row_name} {channel}")

    def test_the_row_reads_name_then_letter_and_field_three_times(self):
        controls = HdrColorControls()
        widgets = row_widgets(controls, controls.skin_spins[0])
        self.assertEqual(
            [type(widget) for widget in widgets[:7]],
            [QLabel, QLabel, QDoubleSpinBox, QLabel, QDoubleSpinBox, QLabel, QDoubleSpinBox],
        )
        self.assertEqual(widgets[0].text(), "Skin RGB:")

    def test_the_letters_did_not_disturb_value_handling(self):
        controls = HdrColorControls()
        controls.sync([2.0, 1.5, 0.25], [4.0, 0.5, 0.125])
        skin, hair = controls.values()
        self.assertEqual(skin, [2.0, 1.5, 0.25])
        self.assertEqual(hair, [4.0, 0.5, 0.125])


if __name__ == "__main__":
    unittest.main()
