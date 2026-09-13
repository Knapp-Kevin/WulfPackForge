"""The save comparison tool names every difference between two character files and writes nothing."""
import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from subscripts.playerDataUtil import pack_player_data_hex
from tests.fixture_saves import realistic_v33_player_data, realistic_v46_root_save, write_fch
from tools.compare_saves import compare, main


def pair(edit_root=None, edit_payload=None):
    """Two files: the v46/v33 fixture and a copy with the given edits applied."""
    payload = realistic_v33_player_data()
    before = realistic_v46_root_save(pack_player_data_hex(payload), name="Frostwulf")
    after = copy.deepcopy(before)
    edited = copy.deepcopy(payload)
    if edit_payload:
        edit_payload(edited)
    after["player_data_hex"] = pack_player_data_hex(edited)
    if edit_root:
        edit_root(after)
    return before, after


class CompareSavesTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.dir = Path(self._temp.name)

    def tearDown(self):
        self._temp.cleanup()

    def _write(self, before, after):
        return str(write_fch(self.dir / "before.fch", before)), str(write_fch(self.dir / "after.fch", after))

    def test_identical_files_report_no_differences(self):
        a, b = self._write(*pair())
        self.assertEqual(compare(a, b), [])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([a, b]), 0)
        self.assertTrue(out.getvalue().rstrip().endswith("0 difference(s)"))
        self.assertIn("container version 46, payload (33, 109, 2)", out.getvalue())

    def test_scalar_and_appearance_changes_are_named(self):
        def hair(p):
            p["hair"] = "Hair38"

        def cheats(r):
            r["used_cheats"] = True
        lines = compare(*self._write(*pair(edit_root=cheats, edit_payload=hair)))
        self.assertEqual(sorted(lines), sorted(["container.used_cheats: False -> True", "payload.hair: 'HairModded99' -> 'Hair38'"]))

    def test_inventory_differences_are_keyed_by_slot(self):
        def edit(p):
            p["inventory"][0]["quality"] = 3                      # SwordBronze at (0,0)
            p["inventory"].pop(2)                                 # the unresolved item at (2,7)
            p["inventory"].append({**p["inventory"][1], "grid_x": 3, "grid_y": 2, "stack": 10})
        lines = compare(*self._write(*pair(edit_payload=edit)))
        self.assertEqual(len(lines), 3, lines)
        self.assertIn("inventory (0, 0) SwordBronze: quality: 2 -> 3", lines)
        self.assertIn("inventory (3, 2): added Wood x10", lines)
        self.assertTrue(any(line.startswith("inventory (2, 7): removed SpearGold_FrostFire") for line in lines), "the fixture's hash now resolves under the 1.0.12 catalogue")

    def test_collections_report_additions_and_removals(self):
        def edit(p):
            p["known_recipes"].append("Recipe_SwordGold_FrostFire")
            p["trophies"].remove("TrophyBoar")
            p["known_material"].reverse()
        lines = compare(*self._write(*pair(edit_payload=edit)))
        self.assertEqual(sorted(lines), sorted(["payload.known_recipes: added 'Recipe_SwordGold_FrostFire'", "payload.trophies: removed 'TrophyBoar'"]))

    def test_a_container_only_change_is_reported(self):
        def rename(r):
            r["character_name"] = "Renamed"
        lines = compare(*self._write(*pair(edit_root=rename)))
        self.assertEqual(lines, ["container.character_name: 'Frostwulf' -> 'Renamed'"])

    def test_records_compare_by_index_and_map_data_as_bytes(self):
        def edit(r):
            r["worlds"][0]["map_data_hex"] = "0102"
            r["stat_records"][0]["stats"][0] = 9.0
        lines = compare(*self._write(*pair(edit_root=edit)))
        self.assertIn("container.worlds[0].map_data: changed (3000 -> 2 bytes)", lines)
        self.assertTrue(any(line.startswith("container.stat_records[0].stats:") for line in lines))

    def test_the_tool_never_writes(self):
        def edit(p):
            p["hair"] = "Hair1"
        a, b = self._write(*pair(edit_payload=edit))
        before_bytes = (Path(a).read_bytes(), Path(b).read_bytes())
        with redirect_stdout(io.StringIO()):
            main([a, b])
        self.assertEqual((Path(a).read_bytes(), Path(b).read_bytes()), before_bytes)


if __name__ == "__main__":
    unittest.main()
