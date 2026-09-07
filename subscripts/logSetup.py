"""One rotating log file under the Wulfpack Forge workspace root, so field failures leave a trace."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from subscripts.workspace import default_workspace_root

HANDLER_NAME = "wulfpack-forge-file"
LOG_FILE_NAME = "wulfpack-forge.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def log_path(root: Optional[Path] = None) -> Path:
    return Path(root or default_workspace_root()) / "logs" / LOG_FILE_NAME


def _existing_handler() -> Optional[logging.Handler]:
    return next((h for h in logging.getLogger().handlers if h.get_name() == HANDLER_NAME), None)


def configure_logging(root: Optional[Path] = None) -> Optional[Path]:
    """Attach the file handler once; return the log path, or ``None`` when the location is unusable."""
    path = log_path(root)
    if _existing_handler() is not None:
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    except OSError as exc:
        print(f"Wulfpack Forge: could not open log file {path}: {exc}", file=sys.stderr)
        return None
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(FORMAT))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    if root_logger.level > logging.INFO or root_logger.level == logging.NOTSET:
        root_logger.setLevel(logging.INFO)
    return path


def detach_logging() -> None:
    """Remove the file handler (tests, or before switching roots)."""
    handler = _existing_handler()
    if handler is not None:
        logging.getLogger().removeHandler(handler)
        handler.close()
