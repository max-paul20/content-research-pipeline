"""Shared Gemini Flash-Lite transport helpers.

Hosts the raw-HTTP call helper, the JSON-object extractor, and the
credential guard used by :mod:`pipeline.agents` and
:mod:`pipeline.report_verifier`. Keeping these here (rather than inside
``agents.py``) means the verifier doesn't need to import from the lens
module just to reach shared transport code.

No SDKs — everything is raw ``requests.post`` through
:func:`pipeline.http_utils.request_with_retries`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

import requests

from . import config
from .http_utils import request_with_retries

logger = logging.getLogger(__name__)

_GEMINI_TIMEOUT = 60


def call_gemini(system_prompt: str, user_text: str, *, operation: str) -> requests.Response | None:
    """Send a single Gemini Flash-Lite request through the shared retry helper.

    Shared transport for every Gemini consumer so they all use the same
    URL, auth, and JSON-mode generation config.
    """

    return request_with_retries(
        lambda: requests.post(
            f"{config.GEMINI_API_ENDPOINT}?key={config.GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_text}]}],
                "generationConfig": {
                    "temperature": config.GEMINI_ANALYSIS_TEMPERATURE,
                    "responseMimeType": "application/json",
                },
            },
            timeout=_GEMINI_TIMEOUT,
        ),
        service="Gemini",
        operation=operation,
        logger=logger,
    )


def parse_gemini_object(raw_text: str) -> Dict[str, Any] | None:
    """Extract a JSON object from Gemini's response.

    Handles clean JSON, JSON wrapped in the Gemini ``candidates`` structure,
    and JSON inside markdown code fences. Mirrors
    :mod:`pipeline.analyzer_legacy` for the array case.
    """

    try:
        api_response = json.loads(raw_text)
        if isinstance(api_response, dict) and "candidates" in api_response:
            text = (
                api_response["candidates"][0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return _extract_json_object(text)
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    return _extract_json_object(raw_text)


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    cleaned = _clean_json_text(text)
    if not cleaned:
        return None

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Gemini JSON object: %.100s...", cleaned)
        return None

    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    return None


def _clean_json_text(text: str) -> str:
    cleaned = re.sub(r"```(?:json)?\s*|```", "", text or "", flags=re.IGNORECASE).strip()
    match = re.search(r"[\[{]", cleaned)
    if match:
        cleaned = cleaned[match.start() :].strip()
    return cleaned


def gemini_credentials_ok() -> bool:
    """Return whether the Gemini API key is set and not a placeholder."""

    return bool(config.GEMINI_API_KEY) and not config._is_placeholder(config.GEMINI_API_KEY)


__all__ = ["call_gemini", "gemini_credentials_ok", "parse_gemini_object"]
