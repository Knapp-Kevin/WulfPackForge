#!/usr/bin/env python3
"""Compare two Valheim character files field by field, through the editor's own codec.

    python tools/compare_saves.py before.fch after.fch

Read-only: both files are read into memory and parsed with the same reader the editor
uses; nothing is written. The output names every field that differs, with the old and
new value, so "the game accepted the edited save" becomes a recorded list of what the
game changed rather than an impression. The inventory is keyed by grid slot; other
lists of records compare by index; map data has no decoder and is compared as opaque
bytes. The last line is the difference count. Exit status is always 0.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from subscripts.fchUtil import parse_save  # noqa: E402
from subscripts.playerDataUtil import unpack_player_data_hex  # noqa: E402

OPAQUE = "map_data_hex"


def load(path: str) -> Tuple[dict, dict]:
    """The container and the decoded payload of one file; the file is only read."""
    root = parse_save(Path(path).read_bytes())
    payload = unpack_player_data_hex(root.get("player_data_hex") or "")
    return root, payload


def _fmt(value) -> str:
    return repr(value) if isinstance(value, str) else str(value)


def diff_scalars(prefix: str, before: dict, after: dict, keys) -> List[str]:
    lines = []
    for key in keys:
        if before.get(key) != after.get(key):
            lines.append(f"{prefix}{key}: {_fmt(before.get(key))} -> {_fmt(after.get(key))}")
    return lines


def diff_collections(prefix: str, before: dict, after: dict, keys) -> List[str]:
    """Lists of scalars as sets (order ignored), dicts as mappings, lists of records by index."""
    lines = []
    for key in keys:
        old, new = before.get(key), after.get(key)
        if isinstance(old, dict) or isinstance(new, dict):
            lines += _diff_mapping(f"{prefix}{key}", old or {}, new or {})
        elif _is_record_list(old) or _is_record_list(new):
            lines += _diff_records(f"{prefix}{key}", old or [], new or [])
        else:
            lines += [f"{prefix}{key}: removed {_fmt(v)}" for v in _missing(old, new)]
            lines += [f"{prefix}{key}: added {_fmt(v)}" for v in _missing(new, old)]
    return lines


def _is_record_list(value) -> bool:
    return isinstance(value, list) and bool(value) and isinstance(value[0], dict)


def _missing(source, other) -> list:
    other_set = set(map(_fmt, other or []))
    return [v for v in (source or []) if _fmt(v) not in other_set]


def _diff_mapping(prefix: str, old: dict, new: dict) -> List[str]:
    lines = [f"{prefix}[{_fmt(k)}]: removed {_fmt(old[k])}" for k in old if k not in new]
    lines += [f"{prefix}[{_fmt(k)}]: added {_fmt(new[k])}" for k in new if k not in old]
    lines += [f"{prefix}[{_fmt(k)}]: {_fmt(old[k])} -> {_fmt(new[k])}" for k in old if k in new and old[k] != new[k]]
    return lines


def _diff_records(prefix: str, old: list, new: list) -> List[str]:
    lines = []
    for index in range(max(len(old), len(new))):
        if index >= len(old) or index >= len(new):
            lines.append(f"{prefix}[{index}]: {'added' if index >= len(old) else 'removed'}")
            continue
        keys = [k for k in dict.fromkeys([*old[index], *new[index]]) if k != OPAQUE]
        lines += diff_scalars(f"{prefix}[{index}].", old[index], new[index], keys)
        if old[index].get(OPAQUE) != new[index].get(OPAQUE):
            lines.append(f"{prefix}[{index}].map_data: changed ({len(old[index].get(OPAQUE) or '') // 2} -> "
                         f"{len(new[index].get(OPAQUE) or '') // 2} bytes)")
    return lines


def _slot(item: dict) -> tuple:
    return (item.get("grid_x"), item.get("grid_y"))


def diff_inventory(before: list, after: list) -> List[str]:
    """Items keyed by grid slot; a moved item is a removal at one slot and an addition at another."""
    old = {_slot(item): item for item in before or []}
    new = {_slot(item): item for item in after or []}
    lines = [f"inventory {slot}: removed {old[slot].get('prefab')}" for slot in old if slot not in new]
    lines += [f"inventory {slot}: added {new[slot].get('prefab')} x{new[slot].get('stack', 1)}" for slot in new if slot not in old]
    for slot in old:
        if slot not in new:
            continue
        a, b = old[slot], new[slot]
        keys = [k for k in dict.fromkeys([*a, *b]) if k not in ("_wire", "grid_x", "grid_y")]
        prefab = a.get("prefab") if a.get("prefab") == b.get("prefab") else f"{a.get('prefab')} -> {b.get('prefab')}"
        lines += diff_scalars(f"inventory {slot} {prefab}: ", a, b, keys)
        lines += diff_scalars(f"inventory {slot} {prefab}: wire.", a.get("_wire", {}), b.get("_wire", {}),
                              ("prefab_hash", "durability_raw", "cheat_flags"))
    return lines


def compare(before_path: str, after_path: str) -> List[str]:
    """Every field that differs between the two files, as one line each."""
    root_a, payload_a = load(before_path)
    root_b, payload_b = load(after_path)
    container_keys = [k for k in dict.fromkeys([*root_a, *root_b]) if k != "player_data_hex"]
    scalars = [k for k in container_keys if not isinstance(root_a.get(k, root_b.get(k)), (list, dict))]
    collections = [k for k in container_keys if k not in scalars]
    lines = diff_scalars("container.", root_a, root_b, scalars)
    lines += diff_collections("container.", root_a, root_b, collections)
    payload_keys = [k for k in dict.fromkeys([*payload_a, *payload_b]) if k != "inventory"]
    p_scalars = [k for k in payload_keys if not isinstance(payload_a.get(k, payload_b.get(k)), (list, dict))]
    lines += diff_scalars("payload.", payload_a, payload_b, p_scalars)
    lines += diff_collections("payload.", payload_a, payload_b, [k for k in payload_keys if k not in p_scalars])
    lines += diff_inventory(payload_a.get("inventory"), payload_b.get("inventory"))
    return lines


def _describe(path: str) -> str:
    root, payload = load(path)
    triple = (payload.get("version"), payload.get("inventory_version"), payload.get("skill_version"))
    return f"{path}: container version {root.get('version')}, payload {triple}, character {root.get('character_name')!r}"


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python tools/compare_saves.py before.fch after.fch", file=sys.stderr)
        return 2
    print(_describe(args[0]))
    print(_describe(args[1]))
    lines = compare(args[0], args[1])
    for line in lines:
        print(line)
    print(f"{len(lines)} difference(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
