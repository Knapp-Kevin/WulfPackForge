"""Read-only summary of what a character file records beyond the editable fields.

Everything here is derived from the parsed save; nothing is written back. Names come from
the item catalog when the prefab is known and fall back to the prefab itself.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from data.biomes import biome_labels
from data.items import resolve_item

UNKNOWN = "Unknown"
STATION_NAMES = {
    "piece_workbench": "Workbench",
    "forge": "Forge",
    "piece_stonecutter": "Stonecutter",
    "piece_cauldron": "Cauldron",
    "piece_artisanstation": "Artisan table",
    "blackforge": "Black forge",
    "piece_magetable": "Galdr table",
    "piece_preptable": "Food preparation table",
}


@dataclass
class CharacterSummary:
    created: str = UNKNOWN
    player_id: str = UNKNOWN
    guardian_power: str = "None"
    world_count: int = 0
    worlds: list = field(default_factory=list)
    biomes: list = field(default_factory=list)
    trophies: list = field(default_factory=list)
    recipes: list = field(default_factory=list)
    stations: list = field(default_factory=list)
    materials: list = field(default_factory=list)
    uniques: list = field(default_factory=list)
    foods: list = field(default_factory=list)


def format_created(unix_seconds) -> str:
    """Creation time as a UTC date, or Unknown when the field is absent or unreadable."""
    if unix_seconds is None:
        return UNKNOWN
    try:
        moment = datetime.fromtimestamp(int(unix_seconds), tz=timezone.utc)
    except (OverflowError, OSError, ValueError, TypeError):
        return UNKNOWN
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def item_label(prefab: str) -> str:
    definition = resolve_item(prefab)
    return definition.display_name if definition else prefab


def item_labels(prefabs) -> list:
    return sorted(item_label(prefab) for prefab in prefabs or ())


def recipe_label(recipe: str) -> str:
    """Recipes are stored as ``Recipe_<prefab>``; show the item the recipe makes."""
    prefab = recipe[len("Recipe_"):] if recipe.startswith("Recipe_") else recipe
    return item_label(prefab)


def station_label(prefab: str) -> str:
    """Stations are building pieces, not items; unknown ones show their prefab without the piece_ prefix."""
    fallback = prefab[len("piece_"):] if prefab.startswith("piece_") else prefab
    return STATION_NAMES.get(prefab, fallback)


def station_labels(stations: dict) -> list:
    return sorted(f"{station_label(name)} (level {level})" for name, level in (stations or {}).items())


def food_labels(foods) -> list:
    return [f"{item_label(food.get('name', ''))} ({food.get('time', 0):.0f}s left)" for food in foods or ()]


def guardian_label(power: str) -> str:
    if not power:
        return "None"
    return power[len("GP_"):] if power.startswith("GP_") else power


def summarize(root_save: dict, player_data: dict) -> CharacterSummary:
    """Build the summary shown on the Record tab; tolerant of missing fields."""
    root, data = root_save or {}, player_data or {}
    player_id = root.get("player_id")
    return CharacterSummary(
        created=format_created(root.get("date_created_unix")),
        player_id=UNKNOWN if player_id is None else str(player_id),
        guardian_power=guardian_label(data.get("guardian_power", "")),
        world_count=len(root.get("worlds") or ()),
        worlds=sorted(root.get("known_worlds") or {}),
        biomes=biome_labels(data.get("known_biomes")),
        trophies=item_labels(data.get("trophies")),
        recipes=sorted(recipe_label(recipe) for recipe in data.get("known_recipes") or ()),
        stations=station_labels(data.get("known_stations")),
        materials=item_labels(data.get("known_material")),
        uniques=item_labels(data.get("uniques")),
        foods=food_labels(data.get("foods")),
    )
