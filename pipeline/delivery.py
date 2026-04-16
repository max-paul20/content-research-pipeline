"""Telegram delivery for generated creative briefs.

Formats script dicts as Telegram messages and sends them to the configured
private channel via the Telegram Bot API.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import requests

from . import config
from .http_utils import request_with_retries
from .knowledge_base import CAMPUS_REGISTRY

logger = logging.getLogger(__name__)

_MAX_MSGS_PER_MINUTE = 20
_MSG_INTERVAL = max(3.5, 60.0 / _MAX_MSGS_PER_MINUTE)

# Telegram's sendMessage hard cap is 4096 chars; keep headroom for trailing
# newlines and any chunk-boundary whitespace we re-add on rejoin.
_TELEGRAM_MESSAGE_LIMIT = 4000


def deliver_scripts(
    scripts: List[Dict[str, Any]],
    test_mode: bool = False,
    *,
    include_details: bool = False,
) -> Dict[str, Any]:
    """Send creative briefs to the Telegram private channel.

    Args:
        scripts: Script dicts from :func:`generate_scripts`, each containing
            ``campus``, ``trend_type``, ``brief``, ``source_url``, and
            ``generated_at``.
        test_mode: If ``True``, log messages but don't send.

    Returns:
        A dict with ``sent`` and ``failed`` counts. When ``include_details`` is
        ``True``, also includes a ``delivered_scripts`` list.
    """

    if not scripts:
        logger.info("No scripts to deliver.")
        return _delivery_result(0, 0, [], include_details)

    dry = test_mode or config.is_test_mode() or config.DRY_RUN

    if not dry and config._is_placeholder(config.TELEGRAM_BOT_TOKEN):
        logger.warning("TELEGRAM_BOT_TOKEN is missing or placeholder; skipping delivery.")
        return _delivery_result(0, 0, [], include_details)

    arizona = [s for s in scripts if s.get("campus") == "uofa"]
    calpoly = [s for s in scripts if s.get("campus") == "calpoly"]

    sent = 0
    failed = 0
    delivered_scripts: List[Dict[str, Any]] = []
    msg_count = 0
    separator_needed = bool(arizona and calpoly)
    total_messages = len(arizona) + len(calpoly) + (1 if separator_needed else 0)

    # Arizona first
    for script in arizona:
        msg = _format_message(script)
        ok = _send_or_log(msg, dry)
        if ok:
            sent += 1
            delivered_scripts.append(script)
        else:
            failed += 1
        msg_count += 1
        if msg_count < total_messages:
            _rate_limit(dry=dry)

    # Separator between campuses
    if separator_needed:
        _send_or_log("---", dry)
        msg_count += 1
        if msg_count < total_messages:
            _rate_limit(dry=dry)

    # Cal Poly second
    for script in calpoly:
        msg = _format_message(script)
        ok = _send_or_log(msg, dry)
        if ok:
            sent += 1
            delivered_scripts.append(script)
        else:
            failed += 1
        msg_count += 1
        if msg_count < total_messages:
            _rate_limit(dry=dry)

    logger.info("Delivery complete: %d sent, %d failed", sent, failed)
    return _delivery_result(sent, failed, delivered_scripts, include_details)


def deliver_report(report: str, test_mode: bool = False) -> Dict[str, Any]:
    """Send a free-form report to the Telegram channel, chunking as needed.

    Reports from the Sonnet writer routinely run 800–1200 words (~5–8k chars),
    which exceeds Telegram's 4096-char sendMessage cap. We split the body at
    paragraph boundaries and send each chunk as its own plain-text message.
    ``parse_mode`` is deliberately omitted — Sonnet emits GFM-style ``**bold**``
    which legacy Telegram Markdown v1 rejects.

    Empty reports and placeholder-token skips are treated as no-ops
    (``{"sent": 0, "failed": 0}``), mirroring :func:`deliver_scripts`. On a
    live run, ``sent`` / ``failed`` are per-chunk counts.
    """

    if not report or not report.strip():
        logger.info("No report body to deliver.")
        return {"sent": 0, "failed": 0}

    dry = test_mode or config.is_test_mode() or config.DRY_RUN

    if not dry and config._is_placeholder(config.TELEGRAM_BOT_TOKEN):
        logger.warning("TELEGRAM_BOT_TOKEN is missing or placeholder; skipping report delivery.")
        return {"sent": 0, "failed": 0}

    chunks = _chunk_text(report, _TELEGRAM_MESSAGE_LIMIT)
    sent = 0
    failed = 0
    for idx, chunk in enumerate(chunks):
        ok = _send_or_log(chunk, dry, parse_mode=None)
        if ok:
            sent += 1
        else:
            failed += 1
        if idx < len(chunks) - 1:
            _rate_limit(dry=dry)
    return {"sent": sent, "failed": failed}


def _format_message(script: Dict[str, Any]) -> str:
    """Format a script dict as a Telegram message."""

    campus = script.get("campus", "")
    campus_details = CAMPUS_REGISTRY.get(campus, {})
    emoji = str(campus_details.get("emoji", ""))
    display = str(campus_details.get("display_name", campus))
    trend_type = script.get("trend_type", "").replace("_", " ").title()

    header = f"{emoji} {display} | {trend_type}"
    body = script.get("brief", "")
    source = script.get("source_url", "")
    timestamp = script.get("generated_at", "")

    parts = [header, "", body]
    if source:
        parts.append(f"\nSource: {source}")
    if timestamp:
        parts.append(f"Generated: {timestamp}")

    return "\n".join(parts)


def _send_or_log(text: str, dry: bool, *, parse_mode: str | None = "Markdown") -> bool:
    """Send a message via Telegram Bot API, or just log it in dry mode.

    ``parse_mode=None`` sends the message as plain text. Callers carrying
    GFM-flavored markdown (e.g., ``deliver_report``) should pass ``None`` so
    Telegram's legacy Markdown v1 parser doesn't reject the body.
    """

    label = _message_label(text)

    if dry:
        logger.info("Telegram message ready [dry-run]: %s", label)
        logger.info("[DRY RUN] Would send:\n%s", text)
        return True

    payload: Dict[str, Any] = {
        "chat_id": config.TELEGRAM_CHANNEL_ID,
        "text": text,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode

    response = request_with_retries(
        lambda: requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=15,
        ),
        service="Telegram",
        operation=label,
        logger=logger,
    )

    if response is None:
        return False

    logger.info("Telegram message sent: %s", label)
    return True


def _chunk_text(text: str, limit: int) -> List[str]:
    """Split ``text`` into chunks of at most ``limit`` chars.

    Splits prefer paragraph boundaries (``\\n\\n``), then single newlines,
    then spaces; falls back to a hard cut if no whitespace is found in the
    window. Inter-chunk whitespace is stripped so rejoined output reads
    naturally even though each chunk ships as its own Telegram message.
    """

    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        split_at = window.rfind("\n\n")
        if split_at == -1:
            split_at = window.rfind("\n")
        if split_at == -1:
            split_at = window.rfind(" ")
        if split_at == -1:
            split_at = limit  # no whitespace — hard cut
        piece = remaining[:split_at].rstrip()
        if piece:
            chunks.append(piece)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _message_label(text: str) -> str:
    """Return a short label for logs based on the first content line."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "empty message"
    return lines[0][:80]


def _delivery_result(
    sent: int,
    failed: int,
    delivered_scripts: List[Dict[str, Any]],
    include_details: bool,
) -> Dict[str, Any]:
    """Return the default or expanded delivery result payload."""

    result: Dict[str, Any] = {
        "sent": sent,
        "failed": failed,
    }
    if include_details:
        result["delivered_scripts"] = delivered_scripts
    return result


def _rate_limit(*, dry: bool) -> None:
    """Sleep between sends to stay under Telegram's 20 msgs/minute limit."""

    if dry:
        return
    time.sleep(_MSG_INTERVAL)
