import unittest

from data.biomes import biome_labels
from subscripts.characterSummary import format_created, recipe_label, station_label, summarize
from tests.fixture_saves import realistic_player_data, realistic_root_save


class CharacterSummaryTests(unittest.TestCase):
    def test_summary_reads_the_fixture_character(self):
        summary = summarize(realistic_root_save(), realistic_player_data())
        self.assertEqual(summary.created, "2023-11-14 22:13 UTC")
        self.assertEqual(summary.player_id, str(realistic_root_save()["player_id"]))
        self.assertEqual(summary.guardian_power, "Eikthyr")
        self.assertEqual(summary.worlds, ["WorldA"])
        self.assertEqual(summary.world_count, len(realistic_root_save()["worlds"]))
        self.assertEqual(summary.biomes, ["Meadows", "Swamp", "Mountain"])
        self.assertEqual(summary.trophies, ["Boar Trophy"])
        self.assertEqual(summary.recipes, ["Bronze Sword", "Wood"])
        self.assertEqual(summary.materials, ["Bronze", "Wood"])
        self.assertEqual(summary.stations, ["Forge (level 3)", "Workbench (level 5)"])
        self.assertEqual(len(summary.foods), len(realistic_player_data()["foods"]))

    def test_unknown_values_are_shown_not_dropped(self):
        self.assertEqual(biome_labels([1, 4096, 1]), ["Meadows", "Unknown biome (4096)"])
        self.assertEqual(recipe_label("Recipe_NotAnItem"), "NotAnItem")
        self.assertEqual(station_label("piece_newstation"), "newstation")
        self.assertEqual(format_created(None), "Unknown")
        self.assertEqual(format_created("garbage"), "Unknown")

    def test_string_biomes_render_by_name(self):
        self.assertEqual(biome_labels(["$biome_meadows", "Meadows", "$biome_ocean", "$biome_none"]),
                         ["Meadows", "Ocean", "$biome_none"])
        self.assertEqual(biome_labels(["Black Forest", "BlackForest", "$biome_blackforest"]), ["Black Forest"])
        self.assertEqual(biome_labels([1, 4096, 1]), ["Meadows", "Unknown biome (4096)"])

    def test_the_summary_carries_four_risk_lines(self):
        from tests.fixture_saves import realistic_v33_player_data
        summary = summarize(realistic_root_save(), realistic_v33_player_data())
        self.assertEqual(len(summary.cheat_risk), 4)
        self.assertIn("world cheat state", summary.cheat_risk[-1])
        self.assertEqual(summary.biomes, ["Meadows", "$biome_none"])

    def test_empty_inputs_produce_an_empty_summary(self):
        summary = summarize({}, {})
        self.assertEqual(summary.created, "Unknown")
        self.assertEqual(summary.guardian_power, "None")
        self.assertEqual((summary.world_count, summary.worlds, summary.trophies, summary.recipes), (0, [], [], []))


if __name__ == "__main__":
    unittest.main()
