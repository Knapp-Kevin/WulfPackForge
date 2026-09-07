# Architecture

Wulfpack Forge is intentionally small. Its architecture is organized around one principle: make character editing easy at the surface while keeping save handling conservative underneath.

## Runtime shape

```text
Player
  │
  ▼
PySide6 desktop UI
  │
  ├── character discovery
  ├── appearance / inventory / skills editors
  ├── save-health/status surface
  └── save orchestration
        │
        ├── immutable opened baseline in memory
        │
        ▼
managed Wulfpack Forge workspace
  │     ├── source snapshot
  │     ├── verified working copy
  │     ├── backups
  │     └── metadata / expected source hash
  │
  ▼
Valheim character parser / serializer
  │
  ▼
verification + external-change guard + atomic replacement
  │
  ▼
active local .fch file
```

Wulfpack Forge does not use a server or remote database for normal operation. Character files are read from the local machine. Steam Cloud characters participate only after Steam has synchronized a local copy.

## Major components

### `ui/`

Owns the player-facing desktop experience.

- `mainWindow.py` coordinates loading, workspace creation, editing, health state, and saving; `characterPicker.py` owns discovery and the character row, `brandBanner.py` the banner, and `messages.py` the dialog texts.
- `saveStatusWidget.py` renders compact verification and compatibility state.
- `branding.py` resolves Wulfpack Forge product metadata and bundled assets.
- `appearanceTab.py`, `appearancePreview.py`, and `hdrColorControls.py` own appearance selection, the composed live preview, and guarded HDR colour editing; `newCharacterDialog.py` reuses that appearance surface for creation.
- `inventoryTab.py`, `inventorySlot.py`, and `equipmentPanel.py` own the grid, drag-and-drop interactions, and derived equipped-slot summary; `itemPickerDialog.py` provides the category tree and search, while `itemEditDialog.py` handles constraints and durability-percent editing.
- `glyphs.py` renders, tints, caches, and validates original inventory and appearance artwork, with item fallback behavior resolved by `data/glyphs.py`.
- `skillsTab.py` and `miscTab.py` own their respective controls and data mapping; `fieldTracker.py` supports preserve-by-default write-back.

The UI should not bypass the workspace or save-safety layer.

### `subscripts/valheim_detection.py`

Three-state process scan (running, not running, inconclusive) built on psutil. It has no Qt dependency; the main window imports it and refuses to write while the game runs or while the scan cannot finish.

### `subscripts/saveFlow.py`

Filesystem helpers for Save Changes: staging the verified working copy beside the destination, quiet (but logged) temp-file removal, and external-change detection on error text.

### `subscripts/characterDiscovery.py`

Finds `.fch` files in supported local Valheim directories and Steam userdata locations.

A Steam Cloud entry is discoverable only when a synchronized copy exists on disk. This component does not connect to remote Steam Cloud services.

### `subscripts/fchUtil.py`

Provides Valheim `.fch` structure parsing and compilation behavior inherited and extended from the VikingEditor codebase. Primitive binary readers and writers live in `subscripts/binaryIO.py`.

Normal product flows use the strict verification layer rather than relying on permissive parser behavior alone.

### `subscripts/playerDataUtil.py`

Decodes and repacks the character's inner player-data payload.

### `subscripts/saveHealth.py`

Converts verification, save-version compatibility, source metadata, external-change state, catalog version, and backup state into explicit player-facing status.

Current states:

- `Verified`
- `Compatibility unverified`
- `Needs attention`

A file that parses successfully is not automatically considered writable. Write validation covers character-save versions 40 through 43; player-data version 29, inventory version 106, and skill version 2 are checked separately as the supported inner layout.

### `subscripts/logSetup.py`

Configures the rotating `logs/wulfpack-forge.log` file under the managed workspace root and fails safely when logging cannot be established.

### `subscripts/workspace.py`

Owns Wulfpack Forge's managed editing workspace.

Default roots:

- Windows: `%LOCALAPPDATA%\WulfpackForge`
- macOS: `~/Library/Application Support/WulfpackForge`
- Linux: `$XDG_DATA_HOME/WulfpackForge` or `~/.local/share/WulfpackForge`

Each active character receives a stable workspace containing:

```text
characters/active/<character-id>/
├── source/
├── working/
├── backups/
└── metadata.json
```

When a character is opened, the source must pass strict verification before the workspace is created. The workspace records an immutable source snapshot, a verified working copy, and the expected SHA-256 of the active source. The source snapshot is not edited during the session.

The workspace is deliberately outside Valheim's save tree so Wulfpack Forge's own history is not mistaken for active game state or synchronized by Steam as additional characters.

### `subscripts/saveSafety.py`

Owns the final write-safety boundary:

1. validate generated candidate;
2. verify checksum and structure;
3. reparse and compare expected root data;
4. confirm the active destination still matches the source hash recorded when opened;
5. create a timestamped backup in the managed character workspace;
6. atomically replace the active destination.

If candidate verification or destination consistency fails, replacement must not occur.

### `data/`

Separates discoverability metadata from write policy.

- `items.py` and `valheim_items.json` provide generated item metadata plus curated write constraints and resolution behavior.
- `item_groups.py` and `equipment.py` provide player-facing catalog navigation and equipment-role/slot rules.
- `glyphs.py` and `appearance.py` map catalog data to presentation-only item glyphs and appearance choices.
- `durability.py` and `valheim_durability.json` provide wiki-derived numeric maximum-durability facts and guarded calculations.
- `skills.py` and `powers.py` provide the supported player-facing names for those save fields.

A catalog refresh must not silently alter write constraints.

### `tools/`

- `update_item_catalog.py` generates the versioned vanilla item snapshot and guards against unexpected source-version drift or suspiciously incomplete output.
- `update_item_durability.py` regenerates numeric durability facts from attributed Valheim community wiki item pages.
- `make_app_icon.py` builds the Windows ICO from the approved Frostwulf source mark.

### `tests/`

Provides behavioral evidence for save safety, managed workspaces, external-change protection, status derivation, discovery, catalog handling, UI widgets, branding assets, and related regression boundaries.

## Save lifecycle

### Create

`subscripts/newCharacter.py` synthesises a new character from defaults calibrated against characters created in-game (no embedded game binary): the outer container and player payload are built as dictionaries, serialized through the same codec that round-trips real saves, written to a temporary file in the chosen characters folder, strictly verified, and moved into place only if no file with that name exists. The new file then enters the normal Load path.

### Load

1. Discover or manually select a local `.fch` file.
2. Strictly verify the save envelope/checksum.
3. Parse outer character data.
4. Decode player payload.
5. Create an immutable in-memory baseline.
6. Create a managed workspace with an immutable source snapshot, verified working copy, and expected source hash.
7. Derive the character health/compatibility state.
8. Populate editor tabs.

A save that cannot be verified and protected is not loaded into the normal editing flow.

### Edit

UI controls mutate the working in-memory character representation. The opened baseline remains unchanged during the editing session. The durable workspace source snapshot likewise remains unchanged.

Editor tabs follow **preserve-by-default write-back**: each tab records what every widget reports immediately after a character is loaded and, on Save Changes, writes back only the fields whose widget value differs. Values the widgets cannot represent (an unknown skill ID, a hairstyle or beard missing from the lookup tables, a fourth active food, floating-point precision beyond a spin box) therefore pass through untouched, and a no-op save produces a byte-identical file. Unknown enumerations are shown as explicit "Unknown (raw)" entries rather than replaced with defaults.

This separation supports future semantic diffing and recovery without reconstructing the original state after the fact.

### Save Changes

1. Confirm the active source still matches the expected hash from open time.
2. Collect changes from editor tabs.
3. Repack player data.
4. Serialize the expected root structure in memory.
5. Write a temporary `.fch` candidate inside the managed workspace, never in the Valheim save directory.
6. Strictly verify and reparse the candidate.
7. Copy the verified candidate into the managed workspace as the current working copy.
8. Scan for Valheim again. Only a scan that proves Valheim is closed may continue; a running game or an **inconclusive process scan** (one where at least one process could not be identified) stops here, keeps the working copy, leaves the active file untouched, and tells the player to close Valheim and save again.
9. Stage the working copy next to the destination so the final replace is atomic.
10. At the replacement boundary, re-check the active source hash.
11. Back up the current active destination into the character workspace.
12. Atomically replace the active destination.
13. Update workspace metadata to the newly applied source hash and backup path.
14. Refresh the player-facing health/status surface.

The active Valheim file is never the scratch space, and nothing is written into its directory before the second process scan passes.

## External-change protection

Steam synchronization creates a special race for save editors: a character can be valid when opened and still be changed by another machine or process before the user clicks Save Changes.

Wulfpack Forge records the active source SHA-256 at open time and compares it again before replacement. A mismatch is treated as a concurrency conflict, not as save corruption. Saving is blocked and the player must reload the newer source.

This guard complements backups. A backup can recover overwritten data after the fact; source-consistency checking avoids performing the stale overwrite in the first place.

## Packaging

`WulfpackForge.spec` defines the PyInstaller package.

The bundle includes:

- Python application/runtime code;
- `data/valheim_items.json`;
- `data/valheim_durability.json`;
- `assets/wulfpack-forge-banner.jpg` and `assets/FrostWulf-favicon.png`;
- the embedded `assets/wulfpack-forge.ico` Windows icon;
- `assets/glyphs/items/` with 34 original inventory masters;
- all hairstyle and beard thumbnails under `assets/glyphs/hair/` and `assets/glyphs/beard/`.

The packaged smoke test verifies that critical generated, branding, and glyph assets can be resolved and decoded from the PyInstaller runtime environment. It checks objective runtime properties, not subjective art quality.

## Compatibility boundary

Game-version compatibility is explicit state, not an assumption.

The parser reads character-save versions 40 and newer exactly and refuses older layouts with a clear error. Writing is enabled for character-save versions 40 through 43 (each round-tripped byte-identical on real saves) whose player payload reports player-data version 29, inventory version 106, and skill version 2; any other combination is inspectable but read-only (`Compatibility unverified`). Both decoders reject a save that leaves bytes unconsumed, so a newer layout can never be silently truncated on save.

A new Valheim version can affect:

- item catalog contents;
- save version fields;
- serialized player structures;
- accepted ranges or semantics;
- in-game acceptance of edited saves.

Major versions therefore require evidence beyond unit tests. See `GOVERNANCE.md` and issue #2.

## Extension rules

New editor capabilities should:

- preserve unrelated data;
- remain human-readable in the normal UI;
- keep raw/modded escape hatches when appropriate;
- use the managed workspace rather than inventing parallel backup behavior;
- preserve the immutable opened baseline when practical;
- add tests at the narrowest stable boundary;
- avoid coupling UI widgets directly to unsafe file replacement logic.

The architecture should remain boring where possible. Boring save code is a feature.
