"""Three-state Valheim process detection.

A scan that cannot identify every process is *inconclusive*, never "not
running": Wulfpack Forge must not overwrite a character file on the strength
of a check it could not complete (GOVERNANCE invariant #1).
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


class ScanState(str, Enum):
    RUNNING = "running"
    NOT_RUNNING = "not_running"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ValheimScan:
    state: ScanState
    process: Optional[dict] = None
    detail: str = ""


def _process_name(proc) -> Optional[str]:
    """Return the process name, or None when it cannot be read."""
    try:
        return proc.info.get("name")
    except psutil.AccessDenied:
        return None


def scan_valheim() -> ValheimScan:
    unreadable = 0
    try:
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = _process_name(proc)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            if name is None:
                unreadable += 1
                continue
            if "valheim" in name.lower():
                info = {"pid": proc.info.get("pid"), "name": name, "exe": proc.info.get("exe")}
                return ValheimScan(ScanState.RUNNING, process=info)
    except (psutil.Error, OSError) as exc:
        logger.warning("Valheim process scan failed: %s", exc)
        reason = str(exc) or " ".join(str(arg) for arg in exc.args) or type(exc).__name__
        return ValheimScan(ScanState.INCONCLUSIVE, detail=f"The process scan failed: {reason}")

    if unreadable:
        plural = "es" if unreadable != 1 else ""
        return ValheimScan(
            ScanState.INCONCLUSIVE,
            detail=f"{unreadable} process{plural} could not be identified, so Valheim may still be running.",
        )
    return ValheimScan(ScanState.NOT_RUNNING)


def is_valheim_running() -> bool:
    return scan_valheim().state == ScanState.RUNNING


def get_valheim_process_info() -> Optional[dict]:
    return scan_valheim().process


def valheim_warning_message(scan: Optional[ValheimScan] = None) -> str:
    scan = scan or scan_valheim()
    if scan.state == ScanState.RUNNING:
        info = scan.process or {}
        return (
            "WARNING: Valheim is currently running!\n\n"
            f"Process Name: {info.get('name')}\n"
            f"Process ID: {info.get('pid')}\n"
            f"Executable: {info.get('exe')}\n\n"
            "Please close Valheim before using this editor to avoid potential conflicts."
        )
    if scan.state == ScanState.INCONCLUSIVE:
        return f"Wulfpack Forge could not confirm that Valheim is closed. {scan.detail}"
    return "Valheim is not currently running."
