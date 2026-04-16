"""Claude Sonnet insight-report writer.

Takes the merged enriched-analysis dict (engagement + trends + competitors
+ content classification) and produces a markdown brief via the Anthropic
Messages API. Raw ``requests.post`` — no SDK. The system block carries
``cache_control: {"type": "ephemeral"}`` so the skill prompt is served from
the prompt cache on subsequent runs.

This module owns no retry logic of its own. The verifier owns the
report-quality retry loop; ``request_with_retries`` handles transient HTTP
failures inside one regeneration attempt.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

import requests

from . import config
from .http_utils import request_with_retries
from .skills import load_skill

logger = logging.getLogger(__name__)

_REPORT_MAX_TOKENS = 4096
_ANTHROPIC_TIMEOUT = 90
_FALLBACK_REPORT = (
    "# Unigliss Trend Radar — unavailable\n\n"
    "Report generation failed for this cycle. Check pipeline logs for the "
    "underlying Anthropic error and rerun.\n"
)


async def generate_report(
    enriched_analysis: Dict[str, Any],
    *,
    test_mode: bool = False,
    retry_instructions: str | None = None,
) -> str:
    """Generate the Unigliss Trend Radar insight report.

    Args:
        enriched_analysis: Dict shaped like the output of
            :func:`pipeline.agents.run_parallel_analysis` — keys
            ``engagement``, ``trends``, ``competitors``, ``contentThemes``.
        test_mode: When ``True`` (or :func:`config.is_test_mode`), return a
            deterministic mock report and skip the Anthropic call.
        retry_instructions: Optional verifier feedback appended to the user
            turn so the writer can fix specific issues on regeneration.

    Returns:
        The markdown report text. On Anthropic failure or a missing API key,
        returns a minimal fallback report rather than raising.
    """

    return await asyncio.to_thread(
        _generate_report_sync,
        enriched_analysis,
        test_mode,
        retry_instructions,
    )


def _generate_report_sync(
    enriched_analysis: Dict[str, Any],
    test_mode: bool,
    retry_instructions: str | None,
) -> str:
    if test_mode or config.is_test_mode():
        return _mock_report(enriched_analysis)

    if config._is_placeholder(config.ANTHROPIC_API_KEY):
        logger.warning("ANTHROPIC_API_KEY missing or placeholder; skipping report generation.")
        return _FALLBACK_REPORT

    system_prompt = load_skill("report-writer")
    user_text = _build_user_text(enriched_analysis, retry_instructions)

    response = request_with_retries(
        lambda: requests.post(
            config.ANTHROPIC_API_URL,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.ANTHROPIC_MODEL,
                "max_tokens": _REPORT_MAX_TOKENS,
                "system": [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [{"role": "user", "content": user_text}],
            },
            timeout=_ANTHROPIC_TIMEOUT,
        ),
        service="Anthropic",
        operation="report writer",
        logger=logger,
    )

    if response is None:
        return _FALLBACK_REPORT

    return _extract_text(response.text) or _FALLBACK_REPORT


def _build_user_text(
    enriched_analysis: Dict[str, Any],
    retry_instructions: str | None,
) -> str:
    """Serialize the analysis JSON and optionally append verifier feedback."""

    body = json.dumps(enriched_analysis, indent=2, default=str)
    if not retry_instructions:
        return body
    return (
        f"{body}\n\n"
        "## retry_instructions\n"
        "The previous draft failed verification. Address each item below in this regeneration:\n\n"
        f"{retry_instructions.strip()}"
    )


def _extract_text(raw_text: str) -> str:
    """Pull the assistant's text body out of an Anthropic Messages response."""

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Anthropic response: %.100s...", raw_text)
        return ""

    if not isinstance(data, dict):
        return ""

    content = data.get("content")
    if not isinstance(content, list):
        return ""

    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str):
                return text.strip()

    return ""


def _mock_report(enriched_analysis: Dict[str, Any]) -> str:
    """Deterministic mock report for dry runs."""

    counts = {
        "engagement_top": len(enriched_analysis.get("engagement", {}).get("topPerformers", [])),
        "emerging": len(enriched_analysis.get("trends", {}).get("emergingTrends", [])),
        "competitor_insights": len(
            enriched_analysis.get("competitors", {}).get("competitorInsights", [])
        ),
        "themes": len(enriched_analysis.get("contentThemes", {}).get("contentThemes", [])),
    }
    return (
        "# Unigliss Trend Radar — mock cycle, UTC\n\n"
        "## TL;DR\n"
        "- Mock report generated in test_mode; no Anthropic call was made.\n"
        f"- Engagement top performers: {counts['engagement_top']}\n"
        f"- Emerging trends: {counts['emerging']}\n"
        f"- Competitor insights: {counts['competitor_insights']}\n"
        f"- Classified themes: {counts['themes']}\n\n"
        "## Emerging Opportunities\nNone in mock mode.\n\n"
        "## What to Skip or Remix\nNone in mock mode.\n\n"
        "## Competitor Watch\nNone in mock mode.\n\n"
        "## Campus Split\n### Arizona\nNone in mock mode.\n### Cal Poly\nNone in mock mode.\n\n"
        "## Signal Quality\nMock report — all four analyst inputs were synthesized for dry-run plumbing only.\n"
    )


__all__ = ["generate_report"]
