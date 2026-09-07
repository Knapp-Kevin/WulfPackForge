#!/usr/bin/env python3
"""Generate a versioned vanilla Valheim item catalog from JotunnDoc.

The generated catalog is intentionally data-only. Runtime safety constraints such as
stack/quality/variant limits remain curated in Wulfpack Forge so a source refresh
cannot silently make save-writing rules more permissive or destructive.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_SOURCE = "https://valheim-modding.github.io/Jotunn/data/objects/item-list.html"
CURRENT_STABLE_VERSION = "0.221.12"


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--expected-version", default=CURRENT_STABLE_VERSION)
    parser.add_argument("--output", default="data/valheim_items.json")
    args = parser.parse_args()

    document = parse_catalog(fetch_text(args.source), args.source, args.expected_version)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Wrote {document['item_count']} catalog rows "
        f"({document['selectable_item_count']} selectable) for Valheim {document['game_version']} "
        f"to {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
