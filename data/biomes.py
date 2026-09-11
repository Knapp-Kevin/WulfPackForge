"""Valheim biomes as stored in a character's known-biome list.

Saves before Valheim 1.0 hold ``Heightmap.Biome`` flag values; 1.0 saves hold strings, either
a localisation token such as ``$biome_meadows`` or a bare spelling such as ``Meadows`` or
``Black Forest``, and one save can hold both for the same biome.
"""

BIOME_NAMES = {
    1: "Meadows",
    2: "Swamp",
    4: "Mountain",
    8: "Black Forest",
    16: "Plains",
    32: "Ashlands",
    64: "Deep North",
    256: "Ocean",
    512: "Mistlands",
}
_TOKEN_PREFIX = "$biome_"


def _biome_key(text: str) -> str:
    """A spelling-insensitive key: ``$biome_blackforest``, ``BlackForest`` and ``Black Forest`` agree."""
    text = text.lower()
    if text.startswith(_TOKEN_PREFIX):
        text = text[len(_TOKEN_PREFIX):]
    return text.replace(" ", "")


_BY_KEY = {_biome_key(name): name for name in BIOME_NAMES.values()}
BIOME_TOKENS = {f"{_TOKEN_PREFIX}{key}": name for key, name in _BY_KEY.items()}


def biome_label(value) -> str:
    """A display name for one stored biome value; an unknown int keeps its number, an unknown string itself."""
    if isinstance(value, str):
        return _BY_KEY.get(_biome_key(value), value)
    return BIOME_NAMES.get(value, f"Unknown biome ({value})")


def biome_labels(values) -> list:
    """Display names for a stored list, in the game's own order, each biome listed once."""
    seen, labels = set(), []
    for value in values or ():
        label = biome_label(value)
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels
