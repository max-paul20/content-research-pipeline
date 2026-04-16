"""Parallel Gemini Flash-Lite analysis agents.

Each agent loads a markdown skill from ``skills/`` as its system prompt,
sends the same scraped-posts batch to Gemini via the shared retry helper,
and returns a JSON-shaped dict. ``run_parallel_analysis`` runs all four
agents concurrently with ``asyncio.to_thread`` and merges the results;
exceptions in one agent never break the run.

No SDKs — everything is raw ``requests.post`` through
:func:`pipeline.http_utils.request_with_retries`, matching the rest of the
pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Dict, List

import requests

from . import config
from .http_utils import request_with_retries
from .skills import load_skill

logger = logging.getLogger(__name__)


_GEMINI_TIMEOUT = 60


def _safe_default(agent: str) -> Dict[str, Any]:
    if agent == "engagement":
        return {"topPerformers": [], "engagementPatterns": {}}
    if agent == "trends":
        return {"emergingTrends": [], "fadingTrends": []}
    if agent == "competitors":
        return {"competitorInsights": [], "gapOpportunities": []}
    if agent == "contentThemes":
        return {"contentThemes": [], "performanceByTheme": {}}
    return {}


def _format_posts(posts: List[Dict[str, Any]]) -> str:
    summaries = []
    for post in posts:
        summaries.append(
            {
                "post_id": post.get("post_id", ""),
                "platform": post.get("platform", ""),
                "author": post.get("author", ""),
                "author_followers": post.get("author_followers", 0),
                "caption": post.get("caption", ""),
                "hashtags": post.get("hashtags", []),
                "views": post.get("views", 0),
                "likes": post.get("likes", 0),
                "comments": post.get("comments", 0),
                "shares": post.get("shares", 0),
                "saves": post.get("saves", 0),
                "url": post.get("url", ""),
                "audio_name": post.get("audio_name", ""),
                "audio_author": post.get("audio_author", ""),
                "posted_at": post.get("posted_at", ""),
                "scraped_at": post.get("scraped_at", ""),
            }
        )
    return json.dumps(summaries, indent=2)


def call_gemini(system_prompt: str, user_text: str, *, operation: str) -> requests.Response | None:
    """Send a single Gemini Flash-Lite request through the shared retry helper.

    Shared with :mod:`pipeline.report_verifier` so both layers use the same
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
    and JSON inside markdown code fences. Mirrors :mod:`pipeline.analyzer`
    for the array case.
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


def _run_agent(
    agent: str,
    skill_name: str,
    posts: List[Dict[str, Any]],
    test_mode: bool,
) -> Dict[str, Any]:
    """Shared sync body for every Gemini lens agent."""

    if test_mode or config.is_test_mode():
        return _safe_default(agent)

    if not gemini_credentials_ok():
        logger.warning(
            "GEMINI_API_KEY missing or placeholder; %s agent returning safe default.",
            agent,
        )
        return _safe_default(agent)

    if not posts:
        logger.info("%s agent received no posts; returning safe default.", agent)
        return _safe_default(agent)

    system_prompt = load_skill(skill_name)
    user_text = _format_posts(posts)
    response = call_gemini(system_prompt, user_text, operation=f"{agent} agent")
    if response is None:
        return _safe_default(agent)

    parsed = parse_gemini_object(response.text)
    if parsed is None:
        logger.warning("%s agent could not parse Gemini response; using safe default.", agent)
        return _safe_default(agent)
    return parsed


def run_engagement_analyzer(
    posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> Dict[str, Any]:
    """Surface top performers and engagement patterns in this batch."""

    return _run_agent("engagement", "engagement-analysis", posts, test_mode)


def run_trend_detector(
    posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> Dict[str, Any]:
    """Detect emerging and fading trends in this batch."""

    return _run_agent("trends", "trend-detection", posts, test_mode)


def run_competitor_analyzer(
    posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> Dict[str, Any]:
    """Surface competitor tactics and gap opportunities in this batch."""

    return _run_agent("competitors", "competitor-analysis", posts, test_mode)


def run_content_classifier(
    posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> Dict[str, Any]:
    """Classify posts into Unigliss content pillars and trend types."""

    return _run_agent("contentThemes", "content-classification", posts, test_mode)


_AGENTS = (
    ("engagement", "engagement-analysis"),
    ("trends", "trend-detection"),
    ("competitors", "competitor-analysis"),
    ("contentThemes", "content-classification"),
)


async def run_parallel_analysis(
    posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Run all four lens agents concurrently and merge their outputs.

    Exceptions from any single agent are logged and replaced with that
    agent's safe-default shape so a partial failure never breaks the run.
    """

    coros: List[Awaitable[Dict[str, Any]]] = [
        asyncio.to_thread(_run_agent, agent, skill, posts, test_mode)
        for agent, skill in _AGENTS
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)

    merged: Dict[str, Dict[str, Any]] = {}
    for (agent, _skill), result in zip(_AGENTS, results):
        if isinstance(result, BaseException):
            logger.warning("%s agent raised %s; using safe default.", agent, result)
            merged[agent] = _safe_default(agent)
        else:
            merged[agent] = result
    return merged


__all__ = [
    "call_gemini",
    "gemini_credentials_ok",
    "parse_gemini_object",
    "run_engagement_analyzer",
    "run_trend_detector",
    "run_competitor_analyzer",
    "run_content_classifier",
    "run_parallel_analysis",
]
