"""Persistent history helpers for cross-run post deduplication."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

_RETENTION_DAYS = 7


def load_scripted_posts(
    path: Path,
    logger: logging.Logger,
    *,
    now: datetime | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Load scripted-post history and drop expired or invalid entries."""

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read scripted-post history %s: %s. Starting fresh.", path, exc)
        return {}

    if not isinstance(data, dict):
        logger.warning("Scripted-post history %s is not a dict. Starting fresh.", path)
        return {}

    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=_RETENTION_DAYS)
    filtered: Dict[str, Dict[str, Any]] = {}
    expired = 0

    for key, record in data.items():
        if not isinstance(record, dict):
            expired += 1
            continue

        delivered_at = _parse_timestamp(
            record.get("last_delivered_at") or record.get("first_delivered_at")
        )
        if delivered_at is None:
            logger.warning("Dropping scripted-post history entry %s with invalid timestamp.", key)
            expired += 1
            continue
        if delivered_at < cutoff:
            expired += 1
            continue
        filtered[str(key)] = record

    if expired:
        logger.info(
            "Expired %d scripted-post history entries older than %d days.",
            expired,
            _RETENTION_DAYS,
        )

    return filtered


def save_scripted_posts(
    path: Path,
    scripted_posts: Mapping[str, Mapping[str, Any]],
    logger: logging.Logger,
) -> None:
    """Persist scripted-post history to disk."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(scripted_posts, handle, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error("Failed to save scripted-post history %s: %s", path, exc)


def filter_unscripted_posts(
    posts: Iterable[Mapping[str, Any]],
    scripted_posts: Mapping[str, Mapping[str, Any]],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Drop posts that have already produced delivered scripts recently."""

    filtered: List[Dict[str, Any]] = []

    for post in posts:
        identity = post_identity(post)
        if identity and identity in scripted_posts:
            logger.info("Skipping already-scripted post %s before analysis.", identity)
            continue
        filtered.append(dict(post))

    return filtered


def record_scripted_posts(
    scripted_posts: Dict[str, Dict[str, Any]],
    scripts: Iterable[Mapping[str, Any]],
    logger: logging.Logger,
    *,
    delivered_at: str,
) -> int:
    """Update scripted-post history for successfully delivered scripts."""

    recorded = 0

    for script in scripts:
        identity = script_identity(script)
        if not identity:
            logger.warning("Delivered script missing source identity; not recording history.")
            continue

        campus = str(script.get("campus", "")).strip()
        existing = scripted_posts.get(identity)
        campuses = _merge_campuses(existing, campus)

        if existing is None:
            recorded += 1
            scripted_posts[identity] = {
                "first_delivered_at": delivered_at,
                "last_delivered_at": delivered_at,
                "platform": str(script.get("source_platform", "")).strip(),
                "post_id": str(script.get("source_post_id", "")).strip(),
                "url": str(script.get("source_url", "")).strip(),
                "campuses": campuses,
            }
            continue

        existing["last_delivered_at"] = delivered_at
        existing["campuses"] = campuses

    return recorded


def post_identity(post: Mapping[str, Any]) -> str | None:
    """Return the durable identity for a scraped post."""

    return make_identity(
        platform=post.get("platform"),
        post_id=post.get("post_id"),
        url=post.get("url"),
    )


def script_identity(script: Mapping[str, Any]) -> str | None:
    """Return the durable identity for a delivered script's source post."""

    return make_identity(
        platform=script.get("source_platform"),
        post_id=script.get("source_post_id"),
        url=script.get("source_url"),
    )


def make_identity(platform: Any = None, post_id: Any = None, url: Any = None) -> str | None:
    """Build a stable identity from post_id when possible, else fall back to URL."""

    normalized_platform = str(platform or "").strip().lower()
    normalized_post_id = str(post_id or "").strip()
    normalized_url = str(url or "").strip()

    if normalized_platform and normalized_post_id:
        return f"{normalized_platform}:{normalized_post_id}"
    if normalized_url:
        return normalized_url
    return None


def _merge_campuses(existing: Mapping[str, Any] | None, campus: str) -> List[str]:
    """Return a stable list of campuses associated with a source post."""

    campuses = []
    if existing:
        existing_campuses = existing.get("campuses", [])
        if isinstance(existing_campuses, list):
            campuses.extend(str(item).strip() for item in existing_campuses if str(item).strip())

    if campus:
        campuses.append(campus)

    deduped: List[str] = []
    seen = set()
    for item in campuses:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp into a timezone-aware datetime."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None

