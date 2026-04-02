"""Central configuration for the Unigliss content research pipeline.

This module loads environment variables from the project ``.env`` file and
exposes runtime constants for scrapers, Gemini calls, Telegram delivery, and
pipeline-level behavior. Validation is explicit: importing this module does not
print, create directories, or raise on missing secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

from .knowledge_base import SUPPORTED_CAMPUSES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Keep environment loading side-effect free beyond populating process env vars.
load_dotenv(ENV_FILE, override=False)

_PLACEHOLDER_VALUES = {
    "",
    "your-key-here",
    "your-anthropic-key",
    "replace_me",
    "replace-me",
    "your-token-here",
    "your-channel-id",
    "your-bot-token",
    "changeme",
    "todo",
    "null",
    "none",
}
_REQUIRED_API_KEYS = (
    "GEMINI_API_KEY",
    "RAPIDAPI_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "ANTHROPIC_API_KEY",
)


def _get_env_str(name: str, default: str = "") -> str:
    """Read a string environment variable and strip surrounding whitespace."""

    return os.getenv(name, default).strip()


def _get_env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to a default."""

    value = _get_env_str(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    """Read a float environment variable, falling back to a default."""

    value = _get_env_str(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable from common truthy/falsy values."""

    value = _get_env_str(name)
    if not value:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _is_placeholder(value: str) -> bool:
    """Check whether an environment variable value is missing or placeholder."""

    return value.strip().lower() in _PLACEHOLDER_VALUES


def _ensure_directory(path: Path) -> str:
    """Create a directory if needed and return a readable validation status."""

    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if existed:
        return "ok (exists)"
    return "ok (created)"


GEMINI_API_KEY = _get_env_str("GEMINI_API_KEY")
RAPIDAPI_KEY = _get_env_str("RAPIDAPI_KEY")
TELEGRAM_BOT_TOKEN = _get_env_str("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = _get_env_str("TELEGRAM_CHANNEL_ID")
ANTHROPIC_API_KEY = _get_env_str("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _get_env_str("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
ANTHROPIC_API_URL = _get_env_str(
    "ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages"
)

RAPIDAPI_BASE_URL = _get_env_str("RAPIDAPI_BASE_URL", "https://scraptik.p.rapidapi.com")
TIKTOK_ENDPOINTS: Dict[str, str] = {
    "trending": _get_env_str("SCRAPTIK_TIKTOK_TRENDING_ENDPOINT", "/tiktok/trending"),
    "hashtag": _get_env_str("SCRAPTIK_TIKTOK_HASHTAG_ENDPOINT", "/tiktok/hashtag"),
    "audio": _get_env_str("SCRAPTIK_TIKTOK_AUDIO_ENDPOINT", "/tiktok/music"),
}
INSTAGRAM_ENDPOINTS: Dict[str, str] = {
    "reels": _get_env_str("SCRAPTIK_INSTAGRAM_REELS_ENDPOINT", "/instagram/reels"),
    "hashtag": _get_env_str("SCRAPTIK_INSTAGRAM_HASHTAG_ENDPOINT", "/instagram/hashtag"),
}
SCRAPE_LIMIT = _get_env_int("SCRAPE_LIMIT", 20)
VIRALITY_THRESHOLD = _get_env_float("VIRALITY_THRESHOLD", 0.7)

GEMINI_MODEL = _get_env_str("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_API_ENDPOINT = _get_env_str(
    "GEMINI_API_ENDPOINT",
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
)
MAX_GEMINI_CALLS_PER_RUN = _get_env_int("MAX_GEMINI_CALLS_PER_RUN", 500)
GEMINI_ANALYSIS_TEMPERATURE = _get_env_float("GEMINI_ANALYSIS_TEMPERATURE", 0.3)
SCRIPTS_PER_CAMPUS = _get_env_int("SCRIPTS_PER_CAMPUS", 3)
ANALYZER_TOP_N = _get_env_int("ANALYZER_TOP_N", 15)
ANALYZER_MIN_SCORE = _get_env_int("ANALYZER_MIN_SCORE", 50)

RUN_INTERVAL_HOURS = 6
DEFAULT_CAMPUS = None
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
SEEN_POSTS_FILE = DATA_DIR / "seen_posts.json"
SCRIPTED_POSTS_FILE = DATA_DIR / "scripted_posts.json"
DRY_RUN = _get_env_bool("DRY_RUN", False)
TEST_MODE = _get_env_bool("TEST_MODE", False)


def is_test_mode() -> bool:
    """Return whether the pipeline is running in test mode."""

    return bool(TEST_MODE)


def validate_config() -> Dict[str, str]:
    """Validate required configuration and ensure runtime directories exist.

    Returns:
        A dictionary mapping configuration keys to human-readable validation
        statuses that can be printed by a future ``main.py --check`` command.
    """

    status: Dict[str, str] = {
        "DATA_DIR": _ensure_directory(DATA_DIR),
        "LOG_DIR": _ensure_directory(LOG_DIR),
    }

    if is_test_mode():
        for key in _REQUIRED_API_KEYS:
            status[key] = "skipped (TEST_MODE enabled)"
        return status

    for key in _REQUIRED_API_KEYS:
        value = globals()[key]
        if not value:
            status[key] = "missing"
        elif _is_placeholder(value):
            status[key] = "placeholder"
        else:
            status[key] = "ok"

    return status


__all__ = [
    "ANALYZER_MIN_SCORE",
    "ANALYZER_TOP_N",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_API_URL",
    "ANTHROPIC_MODEL",
    "DEFAULT_CAMPUS",
    "DATA_DIR",
    "DRY_RUN",
    "ENV_FILE",
    "GEMINI_ANALYSIS_TEMPERATURE",
    "GEMINI_API_ENDPOINT",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "INSTAGRAM_ENDPOINTS",
    "LOG_DIR",
    "MAX_GEMINI_CALLS_PER_RUN",
    "PROJECT_ROOT",
    "RAPIDAPI_BASE_URL",
    "RAPIDAPI_KEY",
    "RUN_INTERVAL_HOURS",
    "SCRIPTS_PER_CAMPUS",
    "SCRAPE_LIMIT",
    "SEEN_POSTS_FILE",
    "SCRIPTED_POSTS_FILE",
    "SUPPORTED_CAMPUSES",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TEST_MODE",
    "TIKTOK_ENDPOINTS",
    "VIRALITY_THRESHOLD",
    "is_test_mode",
    "validate_config",
]
