# Changelog

All notable user-facing changes to Wulfpack Forge are recorded here.

The project is currently evolving toward its first branded Wulfpack Forge release, so historical work is grouped by implementation milestone rather than retroactively inventing version numbers.

## Unreleased

### Added
- Scanned mod items can be added: the item picker gains a Modded group, branched by the kind of item, and search finds them by the mod's name.
- Item styles chosen by picture. When game icons have been extracted (Inventory > Game Icons), the item editor shows each style of an item such as a cape or shield as its own icon with an approximate colour word ("Style 2 · blue") next to the number, and inventory tiles show the icon of the style they hold. The number field remains for items without extracted icons.
- Mod scan, opt-in. Skills > Mods reads the plugin folder of a BepInEx profile (game folder, Thunderstore Mod Manager, or r2modman, or any folder you choose) so modded skills show their names instead of numbers and modded items show the mod's own name and icon on inventory tiles and in the item editor. Plugin files are only read; no mod code runs; the result is kept in the Wulfpack Forge workspace. Item names and icons need the optional UnityPy package; skills scan without it.
- Game icons on inventory tiles, opt-in. Inventory > Game Icons reads the item icons from your own Valheim installation (found through Steam or a folder you choose) and keeps PNG copies in the Wulfpack Forge workspace; tiles and the item picker then show the real icons, with the bundled fallback art for anything the game has no icon for. The game files are only read, and the copies never leave your computer through Wulfpack Forge. The feature needs the optional UnityPy package (requirements-optional.txt); without it the dialog says so and nothing else changes.
- Character discovery reads Steam's install location from the Windows registry, so Steam Cloud local copies are found when Steam is installed outside Program Files (for example on another drive). The Program Files and STEAM_DIR searches remain as fallbacks.
- A read-only Record tab showing what the character file records beyond the editable fields: creation date, player ID, forsaken power, worlds visited and known world names, known biomes, trophies, known recipes, crafting stations and their levels, known materials, unique items, and active food. Names come from the item catalog; anything unrecognised is shown by its stored name rather than hidden. Nothing on the tab can be edited or written back.

### Fixed
- The vanilla Ride skill (id 110) is named; it showed as Unknown (110).
- Three defensive lifetime fixes found while chasing an intermittent test-suite crash: the banner's settle timer is owned by the banner, the character list stops its background scan when the window closes, and the appearance preview builds its images as Qt-owned copies rather than views over Python buffers. The crash itself was the test harness freeing windows at arbitrary times; test windows are now torn down deterministically.
- An intermittent crash while opening dialogs: widget signals were connected through lambdas that captured the widget, so Python freed the widget at an arbitrary garbage-collection point instead of deterministically. Every connection now targets a bound method, and the structural test refuses the old pattern.
- With no character loaded, the editor tabs are disabled and the status line says to open or create a character. Previously the Inventory tab showed an empty grid whose picker and editor opened but could not add anything, and the failure was silent. Inventory actions now refuse cleanly without a character, and any error that escapes the interface is written to the log file.
- Overbright colours now keep their hue in the head preview and the colour swatches instead of washing to white: the display colour is the stored colour scaled to its peak, and the multiplier shows as a glow (faint at 2×, strong at 8×). Stored values are unchanged.
- HDR intensity presets now scale the colour you picked (Normal 1× restores it exactly, Bright 2× doubles it) instead of re-anchoring to a peak of 1.0, so clicking presets in any order never drifts.
- Beards and moustaches in the head preview are fitted to the face: the beard art is scaled and shifted to the hair image's shoulders instead of being centred, which had left them sitting high.
- The banner now scales with the window: the whole image stays visible at every width, its height follows the image's proportions (between 90 and 260 px), and it renders sharply on high-DPI displays instead of showing a cropped horizontal slice that jumped on resize.
- The item picker only offers things a character can actually carry. Creature attacks (troll log swings, draugr and skeleton weapons, charred greatswords, brute taunts) and internal cheat items no longer appear in any category or search result; the Advanced raw-prefab entry remains for deliberate use.
- Named weapons without a material in their prefab name (Splitnir and its Bleeding, Storming, and Primal variants, Mistwalker, Krom, Nidhögg, Slayer, Ripper, Dyrnwyn, and the rest) now sit under their crafting tier in the picker, such as Weapons › Spears › Flametal. Any type that still has unranked items shows an "Other" branch, so nothing is reachable only from the type node.
- Saving no longer rewrites data you did not change. Modded or unrecognised skill IDs were previously reset to 0, hairstyles and beards missing from the built-in tables were replaced with "none", a fourth active food was dropped, and every skill level, health, and stamina value was rounded. A save without edits now produces a byte-identical file.
- The Valheim-running check no longer treats a scan it could not complete as "not running". An inconclusive scan keeps your verified edit in the Wulfpack Forge workspace, leaves the active character untouched, and asks you to close Valheim and save again.
- Save parsing rejects files with unconsumed trailing data, refuses character-save versions older than 40 with a clear message, preserves non-UTF-8 text exactly, and treats unknown player-data layout versions as read-only instead of writable.
- The `fchUtil.py` command-line `unpack` mode works again.
- `--smoke-test` no longer blocks on the "Valheim Running" dialog when the game happens to be open on the machine running the check.

### Added
- A version marker (`0.9.0-rc.1`) in the window title, the startup log line, and `main.py --version`. Tags with a pre-release suffix now produce a draft pre-release for maintainer validation; only a plain version tag publishes a release.
- The pre-replacement backup is hash-verified before the active character file is replaced; a backup that does not match refuses the save and leaves the active file untouched. The workspace keeps the ten most recent opened snapshots and ten most recent backups per character and prunes older ones. Save failures are reported by kind (character changed outside the editor, verification failed, workspace or file error).
- **Character records.** The character list groups every copy of a character (active save, Valheim's `.fch.old` and backup files, Wulfpack Forge snapshots and backups) under one entry by the identity inside the save. **States…** shows them with kind, location, time, version, and status; a state can be opened or restored as the active save, and a restore goes through the normal Save Changes path with its guard, backup, and atomic replace. The workspace is now keyed by that identity, so a backup opened as a file no longer creates a second workspace. A scan cache keeps repeat discovery cheap.
- A rotating log file under the Wulfpack Forge workspace root (`logs/wulfpack-forge.log`, 1 MB with three backups) so failures to open or save a character leave a trace that can be attached to a bug report.
- Guarded **Advanced HDR / Overbright Colors** controls for skin and shared hair/beard color floats, with explicit opt-in before entering values above 1.0 (from PR #16).
- RGB float controls from `0.0` through `10.0`; negative/underbright values are prohibited at the widget boundary.
- Hue-preserving Normal 1×, Bright 2×, Glow 4×, and Extreme 8× appearance intensity presets, selectable for skin, hair/beard, or both. The head preview follows overbright edits in hue only.
- Inline HDR intensity labels plus warnings for overbright values and stronger warnings above 4.0, where bloom/washout may become extreme in-game.
- Regression coverage proving valid overbright values are preserved without clamping and existing overbright characters round-trip unchanged.
- Durability is edited as a percentage of the item's real maximum for the chosen quality (for example Splitnir: 100 at quality 1, 250 at quality 4), using a new wiki-derived durability table generated by `tools/update_item_durability.py`. Items without known durability, indestructible items, and modded items keep the raw field. Newly added items start at full durability instead of a flat 100, and an item you do not touch keeps its stored value exactly.
- Removing an item no longer requires knowing about right-click: the item editor has a **Remove from Inventory** button, the Delete key works on a selected slot, the confirmation names the item, and a hint under the grid lists every gesture (click, right-click, drag, Delete).
- Live appearance preview: the Appearance tab and the New Character dialog show a large head that updates instantly as you change model, hairstyle, beard, skin colour, or hair colour. It is composed from the bundled style thumbnails, so no new art or game files are needed; beards are hidden on the female model exactly as in the game. Hair and beard choices in the drop-downs now use larger thumbnails.
- **Add All Skills** on the Skills tab gives a character every vanilla skill it lacks at level 0 in one click, and a character with no skills at all (which is how the game writes a brand-new one) now says so instead of showing an empty table.
- Inventory tab refresh: larger illustrated tiles with stack and quality badges, drag-and-drop to move an item to an empty slot or swap two items (only their grid positions change), and an Equipped panel that shows what occupies head, chest, legs, cape, utility, trinket, and each hand. The item picker gets larger tiles, item counts on every tree node, a breadcrumb for the current branch, and the material tier under each name.
- The complete original appearance-art bundle: 38 hairstyle thumbnails and 27 beard thumbnails, plus 11 new inventory glyph masters for bombs, tools, keys, eggs, miscellaneous items, tankards, fishing gear, fist weapons, and scythes.
- The item picker now branches by category, then type, then material (for example Weapons, Swords, Bronze), and separates armour from Hildir's clothing and hats, accessories (belts and trinkets), and creature-only gear. Tooltips show each item's role and equipment slot.
- Equipping an item now follows the game's rule: one item per slot (head, chest, legs, cape, utility, trinket) and hands exclusive between two-handed weapons, shields, and one-handed weapons. Anything that conflicts is unequipped and named in a status line. Saves that already contain conflicting flags are left untouched until you edit one of the items.
- Creature attacks that the catalog source lists as items (troll log swings, draugr and skeleton weapons, charred greatswords, brute taunts) and internal cheat items no longer appear among player weapons. Bombs, pickaxes, tools, keys, eggs, tankards, fishing gear, fist weapons, and the scythe now have their own glyph ids and original art instead of borrowing the sword or greatsword.
- The item editor shows the Variant (Style) field only for items that have styles (such as painted shields) or for modded items the catalog does not know.
- A categorised item picker for adding inventory items: curated groups on the left, an icon grid with search on the right, and an Advanced tab for raw modded prefabs.
- An original 23-piece in-app inventory glyph set with item-aware silhouettes, runtime material tinting, a neutral unknown-item fallback, and a live preview in the item editor.
- Objective runtime and packaged-smoke validation for the complete inventory glyph bundle, plus committed SHA-256 asset hashes.
- **New Character**: create a fresh character file from the main window with name, model, hair, beard, and colours, using the defaults Valheim writes for a new character; verified before placement, never overwrites an existing name, opens immediately for editing.
- **Add Skill** on the Skills tab: give a character any vanilla skill it does not have yet, starting at level 0.
- Hair and beard names now come from the item catalog (all 37 hairstyles and 26 beards, including the previously unnamed `Beard17` to `Beard20`); the "none" choices write the game's own `HairNone` / `BeardNone` values, and an untouched character's empty style is preserved. Hair and beard thumbnails appear automatically when art is present under `assets/glyphs/hair/` and `assets/glyphs/beard/`.
- The Frostwulf mark as the application icon: window and taskbar icon in the running app, and the packaged executable's icon (`assets/FrostWulf-favicon.png`, with `assets/wulfpack-forge.ico` generated by `tools/make_app_icon.py`).
- A one-file Windows source launcher that creates a private Python environment, installs pinned dependencies when needed, and starts Wulfpack Forge.
- Managed Wulfpack Forge character workspaces outside the Valheim save tree.
- Immutable source snapshots captured when a verified character is opened.
- Durable verified working copies before edits are applied to the active save.
- External active-source change detection to prevent overwriting newer Steam, Valheim, or third-party edits.
- Compact character status surface with `Verified`, `Compatibility unverified`, and `Needs attention` states.
- Save version, source, modification time, catalog version, and recent-backup details in the main UI.
- Workspace-scoped timestamped backups.
- Regression coverage for workspace snapshots, working copies, external-change detection, and workspace backup placement.
- Current application screenshots for the main save-status surface, Appearance tab, and catalog-aware Inventory editor.
- Runtime banner validation that rejects non-image bytes instead of accepting a corrupt file based on size alone.
- Regression coverage for banner decoding and save-status text contrast.
- Windows CI smoke coverage for the one-file source launcher.

### Removed
- The Stats tab. Health, stamina, eitr, active foods, guardian power, and the cheat flag are no longer editable; Wulfpack Forge is a character editor, not a cheat panel, and Valheim recalculates the vitals from food anyway. All of those fields still pass through untouched when you save.

### Changed
- CI now lints with pyflakes and enforces an 85 percent coverage floor (`requirements-dev.txt` holds the tools). The `fchUtil.py` command line logs an unknown mode through the logger and prints only its usage text.
- Character discovery runs off the interface thread. The list shows "Scanning for characters…" while it works, the window stays responsive with large save libraries or slow disks, and a refresh requested mid-scan runs once more when the scan finishes.
- The README records that characters created and edited with Wulfpack Forge have been loaded and played in Valheim 0.221.12.
- Hardening pass: the main window imports Qt classes explicitly, load and save failures are written to the log as well as shown, and temp-file cleanup failures are logged instead of ignored. The Valheim process scan and the save-flow filesystem helpers moved below the UI layer (`subscripts/`), and the structural test now also refuses star imports and any Qt import outside `ui/`.
- Internal structure pass under the project's Simplicity Razor: the main window is split into banner, character picker, and save-flow modules, the HDR colour group is its own widget, the binary reader and writer live in `subscripts/binaryIO.py`, and long functions were decomposed. No behaviour changed; a structural test now keeps every file under 250 lines, every function under 40, and nesting at three levels or fewer.
- Overbright mode now substitutes the standard colour picker instead of sitting beside it: the Pick Skin Color and Pick Hair Color buttons are shown when overbright is off, and the RGB rows and presets take their place when it is on. Swatches and intensity labels stay in both modes.
- The normal color picker remains limited to standard SDR colors; overbright values are edited only through the explicit advanced controls so ordinary appearance edits stay simple.
- Character-save versions 40 through 43 are now write-validated (previously only 43), based on byte-identical round trips of real saves of each version; the player-data layout is still checked separately.
- `Save Changes` now applies edits to the active loaded character through the managed workspace safety path rather than asking the player to choose the destination again.
- Backups created during normal editing are kept under the character's Wulfpack Forge workspace instead of cluttering the active Valheim character directory.
- Valid character-save versions outside the current write-validated set are explicitly read-only rather than being treated as silently writable.
- README and support guidance now document the workspace, save-health states, Steam Cloud interaction, and source-change protection.
- The canonical README/application banner was restored from the approved 2048×682 master through a binary-safe local conversion.
- Save-status metadata and guidance now use readable foreground colors on the dark status surface.
- README release media now shows the current application with synthetic, publication-safe character data.
- README availability guidance now states explicitly that no public Windows release exists yet and distinguishes temporary CI artifacts from release downloads.
- README availability guidance now includes a usable run-now path without presenting source setup as a public installer or release.
- The documented Python range now matches the pinned PySide6 runtime requirement; Python 3.12 remains the recommended Windows version.

## Branding and governance milestone

Merged in `3f670f3be6a52c4981cbc48f683c4a872de1d635`.

### Added
- Wulfpack Forge product identity and approved wolf banner.
- Branded application header and packaged-brand asset verification.
- Player-facing guidance for Steam Cloud characters that are not yet synchronized locally.
- First-class repository governance, contribution, support, security, architecture, agent, brand, and community documentation.
- Structured issue and pull-request templates.

### Changed
- Repository renamed to `Knapp-Kevin/WulfPackForge`.
- README rewritten around the player journey, current capabilities, compatibility status, safety model, and contributor pathways.
- Application window branding updated from the generic save-editor name to Wulfpack Forge.

## Versioned item catalog milestone

Merged in `4bee65caa90b9cbfeb49f8e753f6a37e63a0233f`.

### Added
- Generated Valheim item catalog pinned to pre-1.0 build `0.221.12`.
- More than 900 player-selectable vanilla catalog entries.
- Catalog source/version metadata and version-drift safeguards.
- Packaged executable verification that the item catalog is bundled correctly.
- Explicit Valheim 1.0 compatibility gate.

### Changed
- Item discovery moved from a small hand-maintained list to generated game-data-backed metadata.
- Duplicate human-readable names require prefab-disambiguated completion labels rather than arbitrary resolution.

## Player-first distribution milestone

Merged in `05e7c8723b343d1490b03d8fd21f65c279202105`.

### Added
- Self-contained Windows `WulfpackForge.exe` build.
- Portable Windows ZIP package and SHA-256 checksums.
- Packaged executable smoke testing in GitHub Actions.

### Changed
- Normal player workflow moved away from Python/Git setup and toward download-and-run distribution.
- Primary UI simplified around character selection, editing, and Save Changes.

## Discovery and item-aware editing milestone

Merged in `f697e9087c07bc6de53653d608c5c008c8b0337c`.

### Added
- Automatic discovery of locally available Valheim character files, including Steam-synchronized copies on disk.
- Strict verification before loading a character.
- Searchable inventory item selection with human-readable names.
- Safe preservation of unknown and modded prefab IDs and unusual existing values.
- Automated tests for discovery, catalog behavior, Qt item editing, and dependencies.

## Save-safety milestone

Merged in `7b86f23e6c7d19fd71df0e29e45aa4404da308f5`.

### Added
- Write blocking while Valheim is running.
- Candidate-first save compilation.
- Strict SHA-512 envelope verification.
- Round-trip reparsing and expected-structure comparison.
- Timestamped backups before replacement.
- Atomic destination replacement only after verification succeeds.
- Regression tests proving failed verification leaves the destination untouched.

## Project lineage

Wulfpack Forge is based on VikingEditor by miskamero and remains distributed under GPLv3. See `NOTICE` and `LICENSE` for attribution and licensing details.
