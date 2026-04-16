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
from typing import Any, Awaitable, Dict, List

from . import config
from .gemini_utils import call_gemini, gemini_credentials_ok, parse_gemini_object
from .skills import load_skill

logger = logging.getLogger(__name__)


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
    "run_engagement_analyzer",
    "run_trend_detector",
    "run_competitor_analyzer",
    "run_content_classifier",
    "run_parallel_analysis",
]
