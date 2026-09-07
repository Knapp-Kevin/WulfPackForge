"""Generate ``data/valheim_durability.json`` from the Valheim community wiki.

For every equipment prefab in the item catalog the tool fetches the wiki page
(direct title, then a search, then a small alias map), reads the ``id`` and
``durability`` lines of each infobox and the ``Durability`` row of the
"Upgrade information" table, and records ``base`` and ``per_level`` so the
editor can compute the maximum for any quality:

    max(quality) = base + per_level * (quality - 1)

Only numbers leave the wiki; the JSON records the source and its CC BY-SA
attribution. Nothing here reads ripped game files.

Usage: python tools/update_item_durability.py [--output data/valheim_durability.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.item_groups import group_for, pickable_items, subgroup_for  # noqa: E402
from data.items import CATALOG_GAME_VERSION, ItemDefinition  # noqa: E402

API = "https://valheim.fandom.com/api.php"
USER_AGENT = "WulfPackForge durability table builder (https://github.com/Knapp-Kevin/WulfPackForge)"
EQUIPMENT_GROUPS = frozenset({
    "Weapons", "Bows and Ammo", "Shields", "Helmets", "Chest Armor", "Leg Armor",
    "Capes", "Clothing and Hats", "Accessories", "Tools",
})
NO_DURABILITY_SUBGROUPS = frozenset({"Arrows", "Bolts", "Bombs", "Fishing"})
# Pages whose title is not the item's display name.
ALIASES = {
    "SwordNiedhogg": "Nidhögg", "SwordNiedhoggBlood": "Nidhögg the Bleeding",
    "SwordNiedhoggLightning": "Nidhögg the Thundering", "SwordNiedhoggNature": "Nidhögg the Primal",
    "HelmetBronze": "Bronze Armor", "ArmorBronzeChest": "Bronze Armor", "ArmorBronzeLegs": "Bronze Armor",
    "ArmorLeatherLegs": "Leather Armor", "ArmorWolfChest": "Wolf Armor", "ArmorWolfLegs": "Wolf Armor",
    "HelmetTrollLeather": "Troll Set", "ArmorTrollLeatherChest": "Troll Set", "ArmorTrollLeatherLegs": "Troll Set",
    "ArmorRootLegs": "Root Set", "ArmorRagsLegs": "Rag Armor", "ArmorRagsChest": "Rag Armor",
    "ShieldIronSquare": "Iron shield", "HelmetStrawHat": "Straw hat", "SwordIronFire": "Dyrnwyn",
}

_INFOBOX_RE = re.compile(r"\{\{\s*infobox[^{}]*?(?:\{\{[^{}]*\}\}[^{}]*?)*\}\}", re.I | re.S)
_ID_RE = re.compile(r"^\|\s*id\s*=\s*([A-Za-z0-9_]+)", re.M)
_DURABILITY_RE = re.compile(r"^\|\s*durability\s*=\s*([^\n|]+)", re.M | re.I)
_PER_LEVEL_RE = re.compile(r"^\|\s*durability per level\s*=\s*([^\n|]+)", re.M | re.I)
_TABLE_ROW_RE = re.compile(r"^!\s*Durability\s*\n((?:\|[^\n]*\n?)+)", re.M)
_QUALITY_TAB_RE = re.compile(r"===\s*Quality\s+(\d+)\s*===(.*?)(?====\s*Quality|\Z)", re.S)
_PER_PIECE_RE = re.compile(r"Durability per piece:\s*([\d,\.]+)", re.I)
# The wiki lists some set pieces under a sibling's id; pieces of a set share durability.
SAME_AS = {"ArmorRootLegs": "ArmorRootChest", "ArmorTrollLeatherChest": "ArmorTrollLeatherLegs"}


def _number(text: str) -> Optional[float]:
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group()) if match else None


def _table_levels(wikitext: str) -> List[float]:
    match = _TABLE_ROW_RE.search(wikitext)
    if not match:
        return []
    values = [_number(cell) for cell in re.findall(r"^\|\s*([^\n|]+)", match.group(1), re.M)]
    return [value for value in values if value is not None]


def _tabber_levels(wikitext: str) -> List[float]:
    """Per-quality 'Durability per piece' figures from a set page's Quality tabs, in order."""
    found = {}
    for quality, body in _QUALITY_TAB_RE.findall(wikitext):
        match = _PER_PIECE_RE.search(body)
        value = _number(match.group(1)) if match else None
        if value is not None:
            found[int(quality)] = value
    return [found[q] for q in sorted(found)] if found and sorted(found) == list(range(1, len(found) + 1)) else []


def _entry(levels: List[float], per_level_hint: Optional[float], page: str) -> dict:
    per_level = levels[1] - levels[0] if len(levels) >= 2 else per_level_hint
    return {"base": levels[0], "per_level": per_level, "levels": levels, "page": page}


def parse_page(wikitext: str, page: str = "") -> Dict[str, dict]:
    """``{prefab: {base, per_level, levels, page}}`` for every infobox that names an id."""
    table_levels = _table_levels(wikitext)
    set_levels = _tabber_levels(wikitext)
    boxes = _INFOBOX_RE.findall(wikitext)
    result: Dict[str, dict] = {}
    for box in boxes:
        ids = _ID_RE.findall(box)
        if not ids:
            continue
        durability = _DURABILITY_RE.search(box)
        per_level = _PER_LEVEL_RE.search(box)
        box_levels = [_number(durability.group(1))] if durability and _number(durability.group(1)) is not None else []
        levels = table_levels if len(boxes) == 1 and table_levels else box_levels
        if len(levels) <= 1 and set_levels and (not levels or levels[0] == set_levels[0]):
            levels = set_levels
        if not levels:
            continue
        hint = _number(per_level.group(1)) if per_level else None
        for prefab in ids:
            result.setdefault(prefab, _entry(levels, hint, page))
    return result


def _get(params: dict) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_wikitext(title: str) -> Optional[str]:
    data = _get({"action": "parse", "page": title, "prop": "wikitext", "redirects": 1})
    return data.get("parse", {}).get("wikitext", {}).get("*")


def search_titles(text: str, limit: int = 5) -> List[str]:
    data = _get({"action": "query", "list": "search", "srsearch": text, "srlimit": limit})
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def equipment_items() -> List[ItemDefinition]:
    return [
        item for item in pickable_items()
        if group_for(item) in EQUIPMENT_GROUPS and subgroup_for(item) not in NO_DURABILITY_SUBGROUPS
    ]


def _candidate_titles(item: ItemDefinition) -> Iterable[str]:
    if item.prefab in ALIASES:
        yield ALIASES[item.prefab]
    yield item.display_name
    for title in search_titles(item.display_name):
        yield title


def build_table(items: Iterable[ItemDefinition], pause: float = 0.15, log=print) -> Dict[str, dict]:
    table: Dict[str, dict] = {}
    for item in items:
        if item.prefab in table:
            continue
        for title in _candidate_titles(item):
            try:
                text = fetch_wikitext(title)
            except Exception as exc:  # network hiccup: try the next title
                log(f"  {item.prefab}: {title!r} failed ({exc})")
                text = None
            time.sleep(pause)
            if not text:
                continue
            parsed = parse_page(text, title)
            if item.prefab in parsed:
                table.update({prefab: entry for prefab, entry in parsed.items() if prefab not in table})
                break
        else:
            log(f"  no durability for {item.prefab} ({item.display_name})")
    for prefab, sibling in SAME_AS.items():
        if prefab not in table and sibling in table:
            table[prefab] = dict(table[sibling])
    return table


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "data" / "valheim_durability.json"))
    args = parser.parse_args(argv)
    items = equipment_items()
    print(f"{len(items)} equipment prefabs")
    table = build_table(items)
    document = {
        "schema_version": 1,
        "game_version": CATALOG_GAME_VERSION,
        "source": {
            "name": "Valheim Wiki (Fandom) item pages",
            "url": "https://valheim.fandom.com/",
            "license": "Numeric game facts read from pages licensed CC BY-SA 3.0; attribution: Valheim Wiki contributors.",
            "generator": "tools/update_item_durability.py",
        },
        "item_count": len(table),
        "items": dict(sorted(table.items())),
    }
    Path(args.output).write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(table)} entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
