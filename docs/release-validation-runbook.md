# Release validation runbook

This is the operator's checklist for the parts of a release that only a person with the game can do: proving that Valheim accepts a character file Wulfpack Forge wrote, and checking how overbright colours render. Every step names the exact action, the exact command, and the evidence line to record. The automated suite proves the editor round-trips real 1.0 saves byte-for-byte; this runbook proves the game agrees.

Two rules apply throughout.

- **Copy-only.** Never open a live character file for writing outside the editor. Copy the file you want to inspect to a scratch folder first, and only ever compare copies.
- **The game's rewrite is the proof.** Valheim re-serialises the whole character on save. The evidence for "the game accepted the file" is a comparison between the file the editor placed and the file the game wrote back after a session: the intended edits survive, and nothing else the editor touched reverts.

The comparison tool is `tools/compare_saves.py`. It reads two `.fch` files through the editor's own codec, prints one line per differing field with the old and new value, and ends with the difference count. It never writes.

```bash
python tools/compare_saves.py <before.fch> <after.fch>
```

## 0. Preparation

1. Valheim 1.0.20 or later installed and closed. Wulfpack Forge run from source on the branch or tag under validation (`run-wulfpack-forge.cmd`, or `python main.py`).
2. Create a **disposable character in-game** on the current build and play a few minutes so it has an inventory, a known biome and at least one recipe. Log out through the menu so the game writes the file. Do not use a character you care about.
3. Make a scratch folder outside the game's save directories, for example `%USERPROFILE%\Desktop\wpf-validation\`.
4. Note the character's file: `%USERPROFILE%\AppData\LocalLow\IronGate\Valheim\characters_local\<name>.fch`.

Record: the game version shown on the main menu and the Steam build id from `steamapps\appmanifest_892970.acf`.

## 1. Load a real 1.0 character

1. Copy `<name>.fch` to the scratch folder as `01-original.fch`.
2. Open Wulfpack Forge, select the character in the picker.

Expected: the status card reads **Verified**, the save version shows 47 for a character saved by Valheim 1.0.20, the catalogue label reads `Valheim 1.0.20`, the Inventory tab shows the items by name, the Record tab shows known biomes by name and an **Achievement risk** section with four lines. For a character saved by an older Valheim the save version is the file's own, the status adds that saving writes it in the format Valheim 1.0.20 writes, and the Achievement risk section has five lines when the save upgrade clears item cheat flags.

Record: `1. load: Verified, version 47, catalog 1.0.20` (or the older version and the upgrade sentence).

## 2. No-op round trip

1. With the character open and nothing edited, click **Save Changes**.
2. Copy the live file to the scratch folder as `02-noop.fch`.
3. Compare:

```bash
python tools/compare_saves.py 01-original.fch 02-noop.fch
```

Expected, for a character saved by Valheim 1.0.20: `0 difference(s)`. The two headers show the same container version and payload triple. For a character saved by an older Valheim the plain comparison lists the save upgrade; compare with `python tools/compare_saves.py --upgrade 01-original.fch 02-noop.fch` instead, which upgrades the first file in memory and must report `0 difference(s)`.

Record: the last line of the output.

## 3. Appearance-only edit

1. Open the character, change the hairstyle and the skin colour on the Appearance tab, click **Save Changes**.
2. Copy the live file as `03-appearance-editor.fch`.
3. Compare `02-noop.fch` against `03-appearance-editor.fch`.

Expected: exactly the lines `payload.hair: ... -> ...` and `payload.skin_color: ... -> ...` and nothing else.

4. Start Valheim, load the character into any world, look at the character, log out through the menu, close Valheim.
5. Copy the live file as `03-appearance-game.fch` and compare `03-appearance-editor.fch` against it.

Expected: the hair and skin colour lines do **not** appear (the game kept them); any lines that do appear are the game's own bookkeeping (play time, position, foods, stamina). Read them and confirm each is something the game changes on every session.

Record: both comparison outputs, and whether the new hairstyle and colour were visible in-game.

## 4. Inventory edit with a 1.0 item

1. Open the character. On the Inventory tab add a **Frostfire Sword** (`SwordGold_FrostFire`) to an empty slot from the picker's Weapons group, set quality 2, and raise the stack of an existing material. Click **Save Changes**.
2. Copy the live file as `04-inventory-editor.fch`; compare `03-appearance-game.fch` against it.

Expected: an `inventory (x, y): added SwordGold_FrostFire x1` line, an `inventory (x, y) SwordGold_FrostFire: quality` line if the fixture read it at 1, a stack line for the material, and nothing else.

3. Load the character in Valheim, open the inventory, hover the sword, equip it, log out, close Valheim.
4. Copy the live file as `04-inventory-game.fch`; compare `04-inventory-editor.fch` against it.

Expected: the sword is still at its slot (no `removed` line for it); the only inventory lines are ones the session explains (equipped flag, durability wear if it was used). The Achievement risk section on the Record tab still reads `Items flagged as cheated: 0`, because the editor writes a clean cheat byte.

Record: both comparison outputs and whether the sword showed its name, icon and stats in-game.

## 5. Workspace path on a live 1.0 directory

1. With the character open, confirm the status card shows a workspace backup after the saves above.
2. While Wulfpack Forge is open, start Valheim and log the character in and out (the game rewrites the file), close Valheim, then click **Save Changes** in the editor without reloading.

Expected: the save is refused with **Needs attention** and the message that the active file changed after it was opened. Nothing is written. Reload the character, and Save Changes works again.

3. Look in the managed workspace (`<workspace>/characters/<identity>/`): a snapshot, a working copy and timestamped backups exist.

Record: `5. guard: refused stale overwrite; backups present`.

## 6. The game keeps the edits across a restart

1. Start Valheim, load the character, confirm the hairstyle, skin colour and the sword are still there, log out, close Valheim.
2. Copy the live file as `06-final.fch`; compare `04-inventory-game.fch` against it.

Expected: no appearance or inventory lines beyond session bookkeeping.

Record: the comparison output. This closes issue #2 items "Valheim accepts the edited save" and "the intended changes survive in-game".

## 6a. The game's own migration of an older character (migration pair)

This compares the editor's save upgrade with the migration Valheim 1.0.20 itself performs. Valheim keeps a single `.fch.old` copy of the file it migrated, so copy both files at once.

1. Pick a character last saved by a Valheim older than 1.0.20 (save version 43 or 46; Wulfpack Forge's status card shows the version). Before starting the game, copy its `.fch` to the scratch folder as `07-before.fch`.
2. Start Valheim 1.0.20, load the character on the character screen, log out through the menu, close Valheim.
3. Immediately copy the live `.fch` as `07-game.fch` and the live `.fch.old` as `07-game.fch.old`.
4. Compare the editor's upgrade of the old file with the game's file:

```bash
python tools/compare_saves.py --upgrade 07-before.fch 07-game.fch
```

Expected: the only lines are changes the game makes on every load or save: `date_created_unix` (rewritten to a calendar day), play-time statistics, `pseudo_counter`, `build_ui` (the game saves its build menu state on every save, the editor an empty blob), world data if a world was entered, the game's every-load normalisation (an item it cannot resolve dropped, a stack clamped, a variant reset), and a 1.0 item's durability one hundredth lower (the game re-derives it through a float on every load). No line in the statistics records, the known-biome tokens or their order, an item's identity, a pre-1.0 item's durability, the cheat bytes or the payload triple.

Record: the comparison output. This is the plan's migration pair (phase 49, D4.4).

## 6b. An editor-upgraded older character loads in Valheim 1.0.20

1. Use a disposable character last saved by a Valheim older than 1.0.20, or copy the original of the one you use to the scratch folder first. Open it in Wulfpack Forge: the status card reads **Verified**, shows the file's own save version and adds that saving writes it in the format Valheim 1.0.20 writes.
2. Click **Save Changes** without editing. Copy the live file as `08-upgraded.fch`; the status card now shows version 47 without the sentence.
3. Start Valheim 1.0.20, load the character into any world, open the inventory and the skills screen, look at the character, log out, close Valheim.
4. Copy the live file as `08-game.fch`; compare `08-upgraded.fch` against it.

Expected: the character loads with its items, skills and appearance; the only lines are session bookkeeping and the every-load lines listed in 6a.

Record: the comparison output and what the game showed. This is the release gate's in-game evidence for the save upgrade (GOVERNANCE, release validation).

## 7. HDR / overbright colours (optional before release)

The README already states that the game decides the final look. If you want a documented result:

1. Open the character, enable **Advanced HDR / Overbright**, and apply each preset in turn - Normal 1x, Bright 2x, Glow 4x, Extreme 8x - to skin and to hair, saving each and loading in-game.
2. For each, note whether the colour reads as brighter, whether bloom or washout occurs, and at which multiplier the effect stops being usable.

Record: one line per preset. Update the README's HDR section only with what you saw.

## 8. Release ceremony

After every section above has its evidence recorded (in the ledger as an operator-directed validation entry, and as a comment on issue #2 ticking the items):

1. Refresh the seven screenshots under `docs/screenshots/` from the current UI with synthetic data, per the README's rule.
2. Confirm `ui/branding.py` carries the candidate version and the CHANGELOG's Unreleased section is complete.
3. Tag the candidate from `main`: `git tag v0.9.0-rc.2 && git push origin v0.9.0-rc.2`. The Windows workflow builds, smoke-tests and creates a **draft** pre-release with the executable, the zip and checksums.
4. Download the draft's zip, run the executable once on a machine without Python, open the disposable character, and confirm the status card.
5. Publish the draft by hand. The README's availability section is rewritten in the same commit that plain-tags the first non-candidate release.
