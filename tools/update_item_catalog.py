#!/usr/bin/env python3
"""Generate the versioned vanilla Valheim item catalogue.

Two sources. ``--from-game DIR --game-version V`` reads the installed game (bundles and
localisation assets) into catalogue schema 2, the source of truth since Valheim 1.0.
Without it the JotunnDoc item list is parsed as before, which yields schema 1 and is
refused when it would overwrite a schema-2 catalogue. ``--cross-check`` compares a game
document against JotunnDoc and copies asset ids; ``--cross-check-only PATH`` compares an
existing catalogue and exits non-zero on any difference, writing nothing.

The generated catalogue is intentionally data-only. Runtime safety constraints such as
stack/quality/variant limits remain curated in Wulfpack Forge so a source refresh
cannot silently make save-writing rules more permissive or destructive.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.catalogFromGame import cross_check, generate, merge_asset_ids  # noqa: E402

DEFAULT_SOURCE = "https://valheim-modding.github.io/Jotunn/data/objects/item-list.html"
CURRENT_STABLE_VERSION = "1.0.7"


class ItemTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[list[str], list[bool]]] = []
        self.page_text: list[str] = []
        self._row: list[str] | None = None
        self._row_images: list[bool] | None = None
        self._cell_parts: list[str] | None = None
        self._cell_has_image = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
            self._row_images = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []
            self._cell_has_image = False
        elif tag == "img" and self._cell_parts is not None:
            self._cell_has_image = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            text = " ".join("".join(self._cell_parts).split())
            self._row.append(text)
            assert self._row_images is not None
            self._row_images.append(self._cell_has_image)
            self._cell_parts = None
            self._cell_has_image = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append((self._row, self._row_images or []))
            self._row = None
            self._row_images = None

    def handle_data(self, data: str) -> None:
        self.page_text.append(data)
        if self._cell_parts is not None:
            self._cell_parts.append(data)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Wulfpack-Forge-catalog-generator/1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _detect_game_version(parser: ItemTableParser, expected_version: str | None) -> str:
    page_text = " ".join(" ".join(parser.page_text).split())
    match = re.search(r"generated from Valheim\s+([0-9][0-9A-Za-z._-]*)", page_text)
    if not match:
        raise RuntimeError("Could not determine Valheim version from JotunnDoc item list")
    game_version = match.group(1)
    if expected_version and game_version != expected_version:
        raise RuntimeError(
            f"JotunnDoc reports Valheim {game_version}, expected {expected_version}. "
            "Review the game update before refreshing the catalog."
        )
    return game_version


def _rows_to_items(rows) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for cells, images in rows:
        if len(cells) < 6 or cells[0] == "Item":
            continue
        prefab, asset_id, _token, display_name, item_type, _description = (cell.strip() for cell in cells[:6])
        if not prefab or prefab.lower() in seen:
            continue
        seen.add(prefab.lower())
        items.append({
            "prefab": prefab,
            "display_name": display_name or prefab,
            "item_type": item_type,
            "asset_id": asset_id,
            "selectable": bool(images and images[0]),
        })
    items.sort(key=lambda item: item["prefab"].lower())
    return items


def parse_catalog(html: str, source_url: str, expected_version: str | None) -> dict:
    parser = ItemTableParser()
    parser.feed(html)
    game_version = _detect_game_version(parser, expected_version)
    items = _rows_to_items(parser.rows)
    selectable_count = sum(1 for item in items if item["selectable"])
    if len(items) < 300 or selectable_count < 200:
        raise RuntimeError(
            f"Parsed suspiciously small catalog: {len(items)} rows, "
            f"{selectable_count} selectable. Refusing to publish it."
        )

    return {
        "schema_version": 1,
        "game_version": game_version,
        "source": {
            "name": "JotunnDoc item list",
            "url": source_url,
            "note": "Automatically generated from vanilla Valheim game data by JotunnDoc.",
        },
        "item_count": len(items),
        "selectable_item_count": selectable_count,
        "items": items,
    }


def _existing_schema(output: Path) -> int:
    try:
        return int(json.loads(output.read_text(encoding="utf-8")).get("schema_version", 0))
    except (OSError, ValueError):
        return 0


def _write(document: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {document['item_count']} catalog rows ({document['selectable_item_count']} selectable) "
          f"for Valheim {document['game_version']} to {output}")


def _report(differences: list[str]) -> int:
    """Set and type differences fail; selectability differences are reported only (icon presence vs JotunnDoc's judgement)."""
    for line in differences:
        print(f"  cross-check: {line}")
    blocking = [line for line in differences if not line.startswith("selectable differs")]
    print(f"cross-check: {len(differences)} difference(s) against JotunnDoc, {len(blocking)} on prefab set or type")
    return 1 if blocking else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--expected-version", default=CURRENT_STABLE_VERSION)
    parser.add_argument("--output", default="data/valheim_items.json")
    parser.add_argument("--from-game", metavar="DIR", help="generate schema 2 from the installed game folder")
    parser.add_argument("--game-version", help="the version the game's main menu shows; required with --from-game")
    parser.add_argument("--cross-check", action="store_true", help="compare the game document against JotunnDoc and merge asset ids")
    parser.add_argument("--cross-check-only", metavar="PATH", help="compare an existing catalogue against JotunnDoc; write nothing")
    args = parser.parse_args(argv)
    output = Path(args.output)

    if args.cross_check_only:
        existing = json.loads(Path(args.cross_check_only).read_text(encoding="utf-8"))
        return _report(cross_check(existing, parse_catalog(fetch_text(args.source), args.source, args.expected_version)))
    if args.from_game:
        if not args.game_version:
            parser.error("--from-game needs --game-version")
        document = generate(Path(args.from_game), args.game_version)
        if args.cross_check:
            jotunn = parse_catalog(fetch_text(args.source), args.source, args.expected_version)
            _report(cross_check(document, jotunn))
            document = merge_asset_ids(document, jotunn)
            document["source"]["note"] += f" Cross-checked against JotunnDoc for Valheim {jotunn['game_version']}."
        _write(document, output)
        return 0
    if _existing_schema(output) >= 2:
        print(f"Refusing to overwrite the schema-2 catalogue at {output} with a JotunnDoc (schema 1) one; "
              "use --from-game or --cross-check-only.", file=sys.stderr)
        return 1
    _write(parse_catalog(fetch_text(args.source), args.source, args.expected_version), output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
