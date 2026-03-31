"""Shared helpers for platform scrapers."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

import requests

from pipeline.config import RUN_INTERVAL_HOURS, SUPPORTED_CAMPUSES, _PLACEHOLDER_VALUES

HASHTAG_SEEDS: Dict[str, Any] = {
    "beauty": [
        "nailtok",
        "lashtok",
        "makeuptutorial",
        "hairtok",
        "nailart",
        "lashtech",
        "beautytok",
        "skincareroutine",
        "nailsofinstagram",
        "browlamination",
        "gelx",
        "pressonails",
    ],
    "college_lifestyle": [
        "collegelife",
        "sorority",
        "dormlife",
        "collegemakeup",
        "rushweek",
        "bidday",
        "greeklife",
        "collegeaesthetic",
        "dormroom",
        "campuslife",
    ],
    "campus_specific": {
        "uofa": ["uofa", "beardown", "wildcats", "uarizona", "universityofarizona", "tucsonaz"],
        "calpoly": ["calpoly", "calpolyslo", "slo", "sanluisobispo", "mustangs"],
    },
    "trending_formats": [
        "grwm",
        "getreadywithme",
        "asmr",
        "beautyhacks",
        "tutorial",
        "transformation",
        "beforeandafter",
        "dayinmylife",
    ],
}

STANDARD_POST_KEYS = (
    "post_id",
    "platform",
    "author",
    "author_followers",
    "caption",
    "hashtags",
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "url",
    "audio_name",
    "audio_author",
    "posted_at",
    "scraped_at",
    "raw_data",
)

_RELEVANCE_TERMS = {
    "nails",
    "lashes",
    "lash",
    "makeup",
    "skincare",
    "hair",
    "beauty",
    "grwm",
    "get ready with me",
    "tutorial",
    "transformation",
    "before and after",
    "college",
    "campus",
    "sorority",
    "rush",
    "dorm",
    "day in my life",
}

_API_KEY_PLACEHOLDERS = frozenset(_PLACEHOLDER_VALUES)


def _is_missing_api_key(value: str) -> bool:
    """Return True if the API key value is absent or an obvious placeholder."""

    return value.strip().lower() in _API_KEY_PLACEHOLDERS


def utc_now_iso(now: Optional[datetime] = None) -> str:
    """Return an ISO 8601 UTC timestamp with a ``Z`` suffix."""

    current = now or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def current_run_marker(now: Optional[datetime] = None) -> int:
    """Return a stable rotation marker for the current 6-hour run window."""

    current = now or datetime.now(timezone.utc)
    interval_seconds = RUN_INTERVAL_HOURS * 3600
    return int(current.timestamp()) // interval_seconds


@lru_cache(maxsize=None)
def flatten_hashtag_seeds() -> List[str]:
    """Flatten and de-duplicate hashtag seeds while preserving order."""

    ordered: List[str] = []
    seen = set()

    for group in HASHTAG_SEEDS["beauty"] + HASHTAG_SEEDS["college_lifestyle"]:
        normalized = group.lower()
        if normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)

    for campus in SUPPORTED_CAMPUSES:
        for tag in HASHTAG_SEEDS["campus_specific"].get(campus, []):
            normalized = tag.lower()
            if normalized not in seen:
                ordered.append(normalized)
                seen.add(normalized)

    for tag in HASHTAG_SEEDS["trending_formats"]:
        normalized = tag.lower()
        if normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)

    return ordered


def select_rotating_hashtags(run_marker: int, batch_size: int = 9) -> List[str]:
    """Return a rotating subset of hashtags for the current run."""

    hashtags = flatten_hashtag_seeds()
    if not hashtags:
        return []

    size = max(1, min(batch_size, len(hashtags)))
    start = (run_marker * size) % len(hashtags)
    rotated = hashtags[start:] + hashtags[:start]
    return rotated[:size]


def extract_hashtags(text: str) -> List[str]:
    """Extract hashtags from free text and normalize them to lowercase."""

    return _unique_strings(match.lower() for match in re.findall(r"#([A-Za-z0-9_]+)", text or ""))


def normalize_timestamp(value: Any) -> Optional[str]:
    """Normalize a timestamp into ISO 8601 UTC or return ``None``."""

    if value in (None, "", 0):
        return None

    if isinstance(value, (int, float)):
        return _timestamp_from_number(float(value))

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return _timestamp_from_number(float(stripped))
        iso_candidate = stripped.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso_candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return None


def safe_int(value: Any) -> int:
    """Coerce a value to ``int`` or return ``0`` when unavailable."""

    if value in (None, "", False):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        try:
            return int(float(value))
        except (TypeError, ValueError, OverflowError):
            return 0


def get_nested(data: Any, *path: str) -> Any:
    """Traverse nested dict/list structures and return the final value."""

    current = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            try:
                index = int(key)
            except ValueError:
                return None
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def pick_first(*values: Any, default: Any = None) -> Any:
    """Return the first non-empty scalar candidate from a list of values."""

    for value in values:
        if value in (None, "", [], {}):
            continue
        return value
    return default


def build_request_headers(api_key: str, base_url: str) -> Dict[str, str]:
    """Build RapidAPI headers for the configured Scraptik host."""

    host = urlparse(base_url).netloc or base_url.replace("https://", "").replace("http://", "")
    return {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": host,
    }


def build_url(base_url: str, endpoint: str) -> str:
    """Join a base URL and endpoint path into a request URL."""

    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def request_json(
    requester: Callable[..., requests.Response],
    *,
    platform: str,
    endpoint_name: str,
    base_url: str,
    endpoint: str,
    api_key: str,
    params: Dict[str, Any],
    logger: logging.Logger,
    timeout: int = 20,
) -> Optional[Any]:
    """Make a scraper request and return parsed JSON or ``None`` on failure."""

    try:
        response = requester(
            build_url(base_url, endpoint),
            headers=build_request_headers(api_key, base_url),
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.error("%s request failed for %s: %s", platform, endpoint_name, exc)
        return None

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "unknown")
        logger.warning(
            "%s rate limited for %s (retry-after=%s); skipping endpoint this run.",
            platform,
            endpoint_name,
            retry_after,
        )
        return None

    if response.status_code >= 400:
        logger.error(
            "%s request failed for %s with status %s.",
            platform,
            endpoint_name,
            response.status_code,
        )
        return None

    try:
        return response.json()
    except ValueError:
        logger.error("%s returned malformed JSON for %s.", platform, endpoint_name)
        return None


def extract_items(payload: Any) -> List[Dict[str, Any]]:
    """Extract a list of post-like dictionaries from variable API payload shapes."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    preferred_keys = (
        "data",
        "items",
        "aweme_list",
        "posts",
        "post_list",
        "results",
        "media",
        "reels",
    )
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items:
                return items
            continue
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested

    for value in payload.values():
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items:
                return items
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested

    return []


def is_relevant_post(caption: str, hashtags: Sequence[str]) -> bool:
    """Return whether a post looks relevant to beauty or college content."""

    tag_set = {tag.lower().lstrip("#") for tag in hashtags}
    known_tags = set(flatten_hashtag_seeds())
    if tag_set.intersection(known_tags):
        return True

    normalized_caption = re.sub(r"[^a-z0-9]+", " ", (caption or "").lower())
    return any(term in normalized_caption for term in _RELEVANCE_TERMS)


def load_seen_posts(path: Path, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    """Load dedup state from disk or return an empty mapping."""

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read seen-posts cache %s: %s. Starting fresh.", path, exc)
        return {}

    if not isinstance(data, dict):
        logger.warning("Seen-posts cache %s is not a dict. Starting fresh.", path)
        return {}
    return data


def save_seen_posts(path: Path, seen_posts: Dict[str, Dict[str, Any]], logger: logging.Logger) -> None:
    """Persist dedup state to disk."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(seen_posts, handle, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error("Failed to save seen-posts cache %s: %s", path, exc)


def dedupe_posts(
    posts: Sequence[Dict[str, Any]],
    seen_posts: Dict[str, Dict[str, Any]],
    *,
    platform: str,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Filter seen posts and update the dedup cache in-place."""

    new_posts: List[Dict[str, Any]] = []
    for post in posts:
        post_id = str(post.get("post_id", "")).strip()
        if not post_id:
            logger.warning("%s post missing post_id; skipping malformed item.", platform)
            continue

        seen_key = f"{platform}_{post_id}"
        if seen_key in seen_posts:
            record = seen_posts[seen_key]
            logger.info(
                "DEDUP: post %s seen before (first seen: %s, views then: %s, views now: %s)",
                post_id,
                record.get("first_seen", "unknown"),
                record.get("views_first_seen", 0),
                post.get("views", 0),
            )
            record["last_seen"] = post.get("scraped_at")
            record["views_last_seen"] = post.get("views", 0)
            record["times_seen"] = safe_int(record.get("times_seen", 1)) + 1
            record["platform"] = platform
            continue

        seen_posts[seen_key] = {
            "first_seen": post.get("scraped_at"),
            "last_seen": post.get("scraped_at"),
            "views_first_seen": post.get("views", 0),
            "views_last_seen": post.get("views", 0),
            "times_seen": 1,
            "platform": platform,
        }
        new_posts.append(post)

    return new_posts


def _timestamp_from_number(value: float) -> Optional[str]:
    """Convert a numeric timestamp in seconds or milliseconds into ISO UTC."""

    timestamp = value
    if value > 1_000_000_000_000:
        timestamp = value / 1000.0
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def _unique_strings(items: Iterable[str]) -> List[str]:
    """Preserve order while de-duplicating strings."""

    ordered: List[str] = []
    seen = set()
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        ordered.append(normalized)
        seen.add(normalized)
    return ordered
