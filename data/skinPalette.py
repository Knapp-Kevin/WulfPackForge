"""The realistic skin palette of the vanilla-friendly appearance mode.

Valheim stores a skin colour as a tint that multiplies its skin texture; the game's own character
screen offers a neutral grey tint from 1.0 down to 0.3. A published skin-tone scale therefore
cannot be used as absolute colours, or its hue would be applied twice. The ten tones of the Monk
Skin Tone scale (Ellis Monk with Google, 2023, CC BY 4.0) are used here as hue ratios, each at a
lightness spread evenly across the game's own range, with a small lightness nudge on top.
"""
from typing import List, Optional, Sequence, Tuple

MST_TONES: Tuple[str, ...] = ("f6ede4", "f3e7db", "f7ead0", "eadaba", "d7bd96", "a07e56", "825c43", "604134", "3a312a", "292420")
PALETTE_ATTRIBUTION = "Skin tones follow the Monk Skin Tone scale (Google, 2023), CC BY 4.0."
SKIN_FLOOR = 0.3      # the darkest tint the game's own screen produces
SKIN_CEIL = 1.0       # the lightest
LIGHTNESS_NUDGE = 0.07  # how far a tone's lightness may be moved in the palette dialog
_HUE_TOLERANCE = 0.01

Tint = Tuple[float, float, float]


def _hue_ratio(hex_colour: str) -> Tint:
    r, g, b = (int(hex_colour[k:k + 2], 16) for k in (0, 2, 4))
    brightest = max(r, g, b)
    return r / brightest, g / brightest, b / brightest


def _tone_lightness(index: int) -> float:
    """Tone ``index`` (0 to 9) sits evenly between the ceiling and the floor."""
    return SKIN_CEIL - (SKIN_CEIL - SKIN_FLOOR) * index / (len(MST_TONES) - 1)


def palette_tints() -> List[Tint]:
    """The ten palette tints, tone 1 first."""
    return [tuple(c * _tone_lightness(i) for c in _hue_ratio(h)) for i, h in enumerate(MST_TONES)]


def nudged(tint: Sequence[float], delta: float) -> Tint:
    """The same hue at a lightness moved by ``delta``, kept between the floor and the ceiling."""
    brightest = max(tint)
    ratio = tuple(c / brightest for c in tint) if brightest else (1.0, 1.0, 1.0)
    lightness = min(SKIN_CEIL, max(SKIN_FLOOR, brightest + delta))
    return tuple(c * lightness for c in ratio)


def nearest_tone(rgb: Sequence[float]) -> int:
    """The 1-based tone whose hue ratio is closest to ``rgb``'s (lightness ignored)."""
    brightest = max(rgb) or 1.0
    ratio = [c / brightest for c in rgb[:3]]
    distances = [sum(abs(a - b) for a, b in zip(ratio, _hue_ratio(h))) for h in MST_TONES]
    return distances.index(min(distances)) + 1


def is_palette_tint(rgb: Sequence[float]) -> bool:
    """True when ``rgb`` is some tone's hue within tolerance, at a lightness within the nudge of that tone's."""
    if len(rgb) < 3 or min(rgb[:3]) < 0 or max(rgb[:3]) <= 0:
        return False
    brightest = max(rgb[:3])
    ratio = [c / brightest for c in rgb[:3]]
    for index, hex_colour in enumerate(MST_TONES):
        hue_matches = all(abs(a - b) <= _HUE_TOLERANCE for a, b in zip(ratio, _hue_ratio(hex_colour)))
        allowed = (max(SKIN_FLOOR, _tone_lightness(index) - LIGHTNESS_NUDGE), min(SKIN_CEIL, _tone_lightness(index) + LIGHTNESS_NUDGE))
        if hue_matches and allowed[0] - 1e-6 <= brightest <= allowed[1] + 1e-6:
            return True
    return False


def tone_label(index: int) -> Optional[str]:
    """``"Tone 3"`` for a 1-based index inside the scale, else ``None``."""
    return f"Tone {index}" if 1 <= index <= len(MST_TONES) else None
