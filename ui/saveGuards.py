"""Checks that stand between Save Changes and the file, shown to the player as dialogs."""
from PySide6.QtWidgets import QMessageBox

from subscripts.valheim_detection import ScanState, ValheimScan, valheim_warning_message
from ui import messages


def block_for_valheim(parent, scan: ValheimScan, working_path=None, message_box=None) -> bool:
    """True when the save must stop because Valheim is (or may be) running; the dialog says which.

    ``message_box`` is the caller's ``QMessageBox`` name, so a test that patches it on the caller's
    module still catches the dialogs raised here.
    """
    box = message_box or QMessageBox
    if scan.state == ScanState.NOT_RUNNING or (working_path is None and scan.state != ScanState.RUNNING):
        return False
    if working_path is None:
        box.critical(parent, "Close Valheim Before Saving",
                     messages.close_valheim_before_saving(valheim_warning_message(scan)))
    else:
        box.warning(parent, "Changes kept in your Wulfpack Forge working copy",
                    messages.kept_in_working_copy(valheim_warning_message(scan), working_path))
    return True
