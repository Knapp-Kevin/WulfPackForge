"""User-facing dialog texts for the main window, kept apart from the flow that shows them."""
from ui.branding import APP_NAME

STARTUP_RUNNING_INFO = (
    "You can inspect a character while Valheim is open, but saving is blocked until the game is closed."
)
NO_CHARACTER_LOADED = "No character loaded. Choose a character above and click Open Character, or create a new one."
NO_PLAYER_DATA_TITLE = "Character Has No Player Data"
NO_PLAYER_DATA_BODY = "The save container is valid, but it contains no editable player data."
NO_PLAYER_DATA_HEALTH = "The save container contains no editable player data."
SAVE_BUTTON_TIP = (
    "Verify the edited working copy, confirm the active file has not changed externally, back it up, then apply changes."
)


def restoring(state_path: str, head_path: str) -> str:
    import os
    return (f"Restoring {os.path.basename(state_path)} into {os.path.basename(head_path)}. "
            "Nothing is written yet; click Save Changes to apply it with a backup.")


def could_not_open(exc) -> str:
    return ("This save was not loaded because it could not be verified, parsed, and protected safely."
            f"\n\n{exc}")


def close_valheim_before_saving(scan_message: str) -> str:
    return f"{scan_message}\n\n{APP_NAME} will not write a character save while Valheim is running."


def kept_in_working_copy(scan_message: str, working_path: str) -> str:
    return (f"{scan_message}\n\n"
            f"Your edits were verified and kept in the Wulfpack Forge working copy:\n{working_path}\n\n"
            "The active character file was not replaced. Close Valheim and click Save Changes again to apply them.")


def changed_outside(exc) -> str:
    return f"{exc}\n\nYour active character was not replaced. Reload it before applying these edits."


def not_saved(exc) -> str:
    return ("The active character was not replaced unless every verification and source-consistency check completed successfully."
            f"\n\n{exc}")


def saved_ok(destination: str, backup_path) -> str:
    text = f"Changes applied safely to:\n{destination}"
    if backup_path:
        text += f"\n\nPrevious save backed up in the Wulfpack Forge workspace:\n{backup_path}"
    return text + ("\n\nThe working copy passed checksum and round-trip verification, and the active file "
                   "was confirmed unchanged before replacement.")
