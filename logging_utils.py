"""Shared logging configuration for CLI and cron runs."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_LOG_FILE = _PROJECT_ROOT / "data" / "logs" / "pipeline.log"
_CONSOLE_HANDLER_NAME = "unigliss-console"
_FILE_HANDLER_NAME = "unigliss-file"


def configure_logging(level: int = logging.INFO) -> Path:
    """Configure console and rotating file logging once per process."""

    root_logger = logging.getLogger()
    module_logger = logging.getLogger(__name__)
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    if not _has_handler(root_logger, _CONSOLE_HANDLER_NAME):
        console_handler = logging.StreamHandler()
        console_handler.set_name(_CONSOLE_HANDLER_NAME)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if not _has_handler(root_logger, _FILE_HANDLER_NAME):
        try:
            _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                _LOG_FILE,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
        except OSError as exc:
            module_logger.warning("File logging disabled for %s: %s", _LOG_FILE, exc)
        else:
            file_handler.set_name(_FILE_HANDLER_NAME)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    root_logger.setLevel(level)
    return _LOG_FILE


def _has_handler(logger: logging.Logger, name: str) -> bool:
    """Return whether the logger already has a named handler."""

    return any(getattr(handler, "name", None) == name for handler in logger.handlers)
