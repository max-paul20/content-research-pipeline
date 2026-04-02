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


def _send_or_log(text: str, dry: bool) -> bool:
    """Send a message via Telegram Bot API, or just log it in dry mode."""

    label = _message_label(text)

    if dry:
        logger.info("Telegram message ready [dry-run]: %s", label)
        logger.info("[DRY RUN] Would send:\n%s", text)
        return True

    response = request_with_retries(
        lambda: requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHANNEL_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
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
