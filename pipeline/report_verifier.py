"""Gemini Flash-Lite report-quality verifier.

Verifies a generated insight report against the rules in
``skills/report-verification.md`` and returns a structured pass/fail with
optional retry instructions for the writer. Fails open: when the verifier
itself errors (HTTP failure, parse failure, missing key), the report is
treated as passing with a logged warning so a flaky verifier never blocks
delivery.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

from . import config
from .gemini_utils import call_gemini, gemini_credentials_ok, parse_gemini_object
from .skills import load_skill

logger = logging.getLogger(__name__)


def _fail_open() -> Dict[str, Any]:
    return {"overallPass": True, "rules": [], "retryInstructions": None}


async def verify_report(
    report: str,
    enriched_analysis: Dict[str, Any],
    *,
    test_mode: bool = False,
) -> Dict[str, Any]:
    """Run the report through the verifier skill.

    Args:
        report: The markdown report from :func:`pipeline.report_writer.generate_report`.
        enriched_analysis: The same enriched analysis dict the writer received,
            used to detect hallucinated post_ids and trends.
        test_mode: When ``True`` (or :func:`config.is_test_mode`), skip the
            Gemini call and pass.

    Returns:
        A dict with keys ``overallPass`` (bool), ``rules`` (list), and
        ``retryInstructions`` (str | None). Fails open on any verifier error.
    """

    return await asyncio.to_thread(
        _verify_report_sync, report, enriched_analysis, test_mode
    )


def _verify_report_sync(
    report: str,
    enriched_analysis: Dict[str, Any],
    test_mode: bool,
) -> Dict[str, Any]:
    if test_mode or config.is_test_mode():
        return _fail_open()

    if not gemini_credentials_ok():
        logger.warning("GEMINI_API_KEY missing or placeholder; verifier failing open.")
        return _fail_open()

    if not report.strip():
        return {
            "overallPass": False,
            "rules": [{"id": "non-empty-report", "pass": False, "detail": "report was empty"}],
            "retryInstructions": "- Report was empty. Regenerate with the same inputs.",
        }

    system_prompt = load_skill("report-verification")
    user_text = json.dumps(
        {"report": report, "analysis": enriched_analysis},
        indent=2,
        default=str,
    )

    response = call_gemini(system_prompt, user_text, operation="report verifier")
    if response is None:
        logger.warning("Verifier Gemini call failed; failing open.")
        return _fail_open()

    parsed = parse_gemini_object(response.text)
    if parsed is None:
        logger.warning("Verifier returned unparseable JSON; failing open.")
        return _fail_open()

    return _normalize_verdict(parsed)


def _normalize_verdict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce verifier output into the shape the orchestrator depends on."""

    overall = raw.get("overallPass")
    if not isinstance(overall, bool):
        rules = raw.get("rules")
        if isinstance(rules, list) and rules:
            overall = all(bool(r.get("pass", False)) for r in rules if isinstance(r, dict))
        else:
            overall = True

    rules_out = raw.get("rules") if isinstance(raw.get("rules"), list) else []
    retry = raw.get("retryInstructions")
    if not isinstance(retry, str) or not retry.strip():
        retry = None

    return {"overallPass": overall, "rules": rules_out, "retryInstructions": retry}


__all__ = ["verify_report"]
