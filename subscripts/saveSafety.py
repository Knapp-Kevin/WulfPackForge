import hashlib
import os
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from subscripts.fchUtil import parse_save
from subscripts.saveErrors import SaveFormatError


class SaveVerificationError(SaveFormatError):
    """Raised when a compiled Valheim save fails structural verification."""


class DestinationChangedError(SaveVerificationError):
    """The active file changed or vanished after it was opened; nothing may be replaced."""


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_backup_path(
    destination: str,
    timestamp: Optional[datetime] = None,
    backup_directory: Optional[str] = None,
) -> str:
    moment = timestamp or datetime.now(timezone.utc)
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if backup_directory:
        directory = Path(backup_directory)
        directory.mkdir(parents=True, exist_ok=True)
        base = str(directory / f"{Path(destination).name}.{stamp}.bak")
    else:
        base = f"{destination}.{stamp}.bak"

    if not os.path.exists(base):
        return base

    counter = 1
    while os.path.exists(f"{base}.{counter}"):
        counter += 1
    return f"{base}.{counter}"


def create_timestamped_backup(
    destination: str,
    timestamp: Optional[datetime] = None,
    backup_directory: Optional[str] = None,
) -> Optional[str]:
    """Copy an existing destination before it is replaced.

    Returns the backup path, or None when the destination does not yet exist.
    When ``backup_directory`` is provided, the backup is stored there instead of
    beside the active Valheim save.
    """
    if not os.path.isfile(destination):
        return None

    backup_path = _next_backup_path(destination, timestamp, backup_directory)
    shutil.copy2(destination, backup_path)
    return backup_path


def _read_and_validate_checksum(fch_path: str) -> bytes:
    """Validate the outer .fch framing and SHA-512 checksum strictly; return the file bytes."""
    with open(fch_path, "rb") as f:
        file_bytes = f.read()

    if len(file_bytes) < 8:
        raise SaveVerificationError("Save is too short to contain a valid .fch envelope.")

    offset = 0
    zpackage_len = struct.unpack_from("<i", file_bytes, offset)[0]
    offset += 4
    if zpackage_len < 0 or offset + zpackage_len + 4 > len(file_bytes):
        raise SaveVerificationError("Save contains an invalid package length.")

    zpackage_bytes = file_bytes[offset:offset + zpackage_len]
    offset += zpackage_len

    hash_len = struct.unpack_from("<i", file_bytes, offset)[0]
    offset += 4
    if hash_len != hashlib.sha512().digest_size:
        raise SaveVerificationError(
            f"Save contains an unexpected checksum length ({hash_len}); expected 64 bytes."
        )

    if offset + hash_len != len(file_bytes):
        raise SaveVerificationError("Save contains truncated or trailing data outside the .fch envelope.")

    stored_hash = file_bytes[offset:offset + hash_len]
    calculated_hash = hashlib.sha512(zpackage_bytes).digest()
    if calculated_hash != stored_hash:
        raise SaveVerificationError("Save failed SHA-512 checksum verification.")
    return file_bytes


def verify_fch_round_trip(fch_path: str, expected_root: Optional[dict] = None) -> dict:
    """Strictly verify checksum, parseability, and optional expected container data."""
    file_bytes = _read_and_validate_checksum(fch_path)

    try:
        parsed = parse_save(file_bytes)
    except Exception as exc:
        raise SaveVerificationError(f"Save could not be reparsed: {exc}") from exc

    if expected_root is not None and parsed != expected_root:
        raise SaveVerificationError(
            "Save reparsed successfully, but its serialized data differs from the expected container."
        )

    return parsed


def replace_verified_save(
    candidate_path: str,
    destination: str,
    expected_root: Optional[dict] = None,
    backup_directory: Optional[str] = None,
    expected_destination_sha256: Optional[str] = None,
) -> Optional[str]:
    """Verify a candidate, guard the destination, back it up, then atomically replace it."""
    verify_fch_round_trip(candidate_path, expected_root)

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if expected_destination_sha256 is not None:
        if not destination_path.is_file():
            raise DestinationChangedError(
                "The active character file disappeared after it was opened. Reload the character before applying changes."
            )
        if _sha256_file(destination) != expected_destination_sha256:
            raise DestinationChangedError(
                "The active character file changed after it was opened. Reload it before applying changes so newer Steam, Valheim, or external edits are not overwritten."
            )

    destination_sha256 = _sha256_file(destination) if destination_path.is_file() else None
    backup_path = create_timestamped_backup(destination, backup_directory=backup_directory)
    if backup_path is not None and _sha256_file(backup_path) != destination_sha256:
        raise SaveVerificationError(
            f"The backup at {backup_path} does not match the active character file, so the active file was not replaced."
        )
    os.replace(candidate_path, destination)
    return backup_path
