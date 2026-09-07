# Support

Wulfpack Forge is community software. Support is provided through this repository on a best-effort basis.

## Before opening an issue

Check the following first:

1. **Close Valheim.** Wulfpack Forge intentionally blocks writes while the game is running.
2. **Confirm the character exists locally.** Steam Cloud characters must be synchronized to the computer before Wulfpack Forge can discover them.
3. **Click Refresh.** The character list only reflects files currently visible on disk.
4. **Try Browse for Another Save.** If you already know where the `.fch` file is, open it directly.
5. **Read the character status.** `Verified`, `Compatibility unverified`, and `Needs attention` have deliberately different meanings.
6. **Keep workspace snapshots and backups.** Do not delete the character's Wulfpack Forge workspace while investigating a save problem.
7. **Check compatibility status.** Major Valheim updates may require explicit revalidation before Wulfpack Forge is considered compatible.

## Windows source-launcher problems

The current run-now path requires the complete source ZIP and 64-bit Python 3.10 through 3.14. Python 3.12 is recommended.

If `run-wulfpack-forge.cmd` does not start the application:

1. confirm the ZIP was extracted instead of opening the launcher inside the ZIP preview;
2. confirm `main.py` and `requirements.txt` are beside the launcher;
3. confirm the Python launcher was selected when Python was installed;
4. keep the command window open and include its exact error message in a bug report;
5. if the private environment is damaged, delete only `.wulfpack-forge-venv` from the extracted Wulfpack Forge folder and run the launcher again.

The first run downloads the pinned dependencies and therefore needs an internet connection. Later runs reuse the private environment unless the requirements change.

## Steam Cloud characters

Wulfpack Forge does not read remote Steam Cloud storage directly.

If a character is visible on another machine but not this one, allow Steam to synchronize it locally. Launch Valheim to confirm the character appears, exit the game, then refresh Wulfpack Forge.

Do not provide your Steam password or authentication tokens to Wulfpack Forge or to anyone claiming they are required for support.

## Log file

Wulfpack Forge writes a rotating log (1 MB, three backups) to `%LOCALAPPDATA%\WulfpackForge\logs\wulfpack-forge.log` on Windows, or the equivalent workspace root on other systems. Failures to open or save a character are recorded there with the full error. Attach the relevant lines to a bug report; the log contains file paths and error text only.

## Character states

The character list shows one row per character. **States…** lists every copy Wulfpack Forge can see: the active save, Valheim's `.fch.old` and backup files, and the workspace snapshots and backups. **Open state** inspects a copy; **Restore as active** loads it as a pending edit and nothing changes on disk until you click **Save Changes**, which still verifies, backs up the current active file, and replaces it atomically.

## Wulfpack Forge workspace

Wulfpack Forge keeps editing protection outside Valheim's own save directories. On Windows the default workspace root is:

`%LOCALAPPDATA%\WulfpackForge`

Each active character can have:

- immutable source snapshots captured when the character is opened;
- a verified working copy;
- backups captured immediately before an active save is replaced (verified against the active file first; the ten most recent snapshots and ten most recent backups are kept per character);
- metadata recording the source path and expected source hash.

Do not move these files into the Valheim character directory or add the Wulfpack Forge workspace to Steam Cloud synchronization. They are recovery and editing state, not active game saves.

## “Character changed outside Wulfpack Forge”

This warning means the active `.fch` no longer matches the file that Wulfpack Forge originally opened. Steam synchronization, Valheim, another editor, a manual copy, or another process may have changed it.

Wulfpack Forge intentionally refuses to overwrite that newer state. The normal recovery path is:

1. preserve the current Wulfpack Forge workspace;
2. reload the active character from disk;
3. review or re-enter the intended changes against the newer source;
4. save again only after the character returns to a verified writable state.

Do not work around this warning by replacing the newer active file with an older snapshot unless you explicitly intend to restore that older version.

## Character status meanings

### Verified

Checksum and structure verification passed and the character save version is in the current write-validated set. Saving is enabled when Valheim is closed and the active source still matches the opened source.

### Compatibility unverified

The file can be parsed and verified, but its character-save version has not been validated for writing. Inspection is allowed, but Save Changes is disabled. This state is especially important around major Valheim updates.

### Needs attention

The save failed strict verification or the active source changed after it was opened. Read the status detail before taking action.

## What to include in a bug report

Please include:

- Wulfpack Forge version or commit;
- Valheim version;
- Windows version if relevant;
- the status shown by Wulfpack Forge;
- whether the character is local, Steam-synchronized, or modded;
- the action you attempted;
- what you expected;
- what happened instead;
- exact error text when available;
- the matching lines from `logs\wulfpack-forge.log` in the Wulfpack Forge workspace.

For UI problems, screenshots are useful. For save-format problems, use a disposable or sanitized character whenever possible.

## Save files

Do not upload a valuable primary character unless absolutely necessary. Prefer reproducing the issue with a newly created disposable character.

If a save operation failed, preserve:

- the active `.fch`;
- the relevant Wulfpack Forge `source/`, `working/`, and `backups/` files;
- `metadata.json` from the character workspace;
- the error message;
- the Valheim build number.

These artifacts can help establish what was opened, what Wulfpack Forge intended to write, and whether the active source changed externally.

## Feature requests

Feature requests belong in GitHub Issues. Describe the player problem first, then the proposed solution. The durable product roadmap is tracked in [issue #2](https://github.com/Knapp-Kevin/WulfPackForge/issues/2).

## Not supported

The project does not promise support for:

- every modded save format or mod interaction;
- unreleased Valheim builds;
- direct remote Steam Cloud access;
- live-memory editing;
- unofficial third-party builds that differ from this repository;
- recovery of every historically corrupted save.

## Security issues

For sensitive vulnerabilities, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
