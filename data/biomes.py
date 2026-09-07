"""Valheim biome flags as stored in a character's known-biome list (Heightmap.Biome)."""

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


def biome_label(value: int) -> str:
    """A display name for one stored biome value; unknown values keep their number."""
    return BIOME_NAMES.get(value, f"Unknown biome ({value})")


def biome_labels(values) -> list:
    """Display names for a stored list, in the game's own order, without duplicates."""
    seen, labels = set(), []
    for value in values or ():
        if value in seen:
            continue
        seen.add(value)
        labels.append(biome_label(value))
    return labels
