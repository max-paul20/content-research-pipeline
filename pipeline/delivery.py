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

logger = logging.getLogger(__name__)

_CAMPUS_EMOJI = {"uofa": "\U0001f335", "calpoly": "\U0001f40e"}
_CAMPUS_DISPLAY = {"uofa": "Arizona", "calpoly": "Cal Poly"}
_MAX_MSGS_PER_MINUTE = 20
_MSG_INTERVAL = 60.0 / _MAX_MSGS_PER_MINUTE


def deliver_scripts(
    scripts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> Dict[str, int]:
    """Send creative briefs to the Telegram private channel.

    Args:
        scripts: Script dicts from :func:`generate_scripts`, each containing
            ``campus``, ``trend_type``, ``brief``, ``source_url``, and
            ``generated_at``.
        test_mode: If ``True``, log messages but don't send.

    Returns:
        A dict with ``sent`` and ``failed`` counts.
    """

    if not scripts:
        logger.info("No scripts to deliver.")
        return {"sent": 0, "failed": 0}

    dry = test_mode or config.is_test_mode() or config.DRY_RUN

    if not dry and config._is_placeholder(config.TELEGRAM_BOT_TOKEN):
        logger.warning("TELEGRAM_BOT_TOKEN is missing or placeholder; skipping delivery.")
        return {"sent": 0, "failed": 0}

    arizona = [s for s in scripts if s.get("campus") == "uofa"]
    calpoly = [s for s in scripts if s.get("campus") == "calpoly"]

    sent = 0
    failed = 0
    msg_count = 0

    # Arizona first
    for script in arizona:
        msg = _format_message(script)
        ok = _send_or_log(msg, dry)
        if ok:
            sent += 1
        else:
            failed += 1
        msg_count += 1
        _rate_limit(msg_count)

    # Separator between campuses
    if arizona and calpoly:
        _send_or_log("---", dry)
        msg_count += 1
        _rate_limit(msg_count)

    # Cal Poly second
    for script in calpoly:
        msg = _format_message(script)
        ok = _send_or_log(msg, dry)
        if ok:
            sent += 1
        else:
            failed += 1
        msg_count += 1
        _rate_limit(msg_count)

    logger.info("Delivery complete: %d sent, %d failed", sent, failed)
    return {"sent": sent, "failed": failed}


def _format_message(script: Dict[str, Any]) -> str:
    """Format a script dict as a Telegram message."""

    campus = script.get("campus", "")
    emoji = _CAMPUS_EMOJI.get(campus, "")
    display = _CAMPUS_DISPLAY.get(campus, campus)
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

    if dry:
        logger.info("[DRY RUN] Would send:\n%s", text)
        return True

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHANNEL_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error("Telegram send failed: %s", exc)
        return False

    if response.status_code != 200:
        logger.error(
            "Telegram returned %d: %s",
            response.status_code,
            response.text[:200],
        )
        return False

    return True


def _rate_limit(msg_count: int) -> None:
    """Sleep if needed to stay under Telegram's 20 msgs/minute limit."""

    if msg_count > 0 and msg_count % _MAX_MSGS_PER_MINUTE == 0:
        logger.info("Rate limit pause (sent %d messages)", msg_count)
        time.sleep(_MSG_INTERVAL)
