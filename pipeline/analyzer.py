"""Tier 1 trend analysis via Gemini Flash-Lite.

Batches raw scraped posts into Gemini API calls, parses structured JSON
scores, computes a composite ranking, and returns the top candidates for
script generation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List

import requests

from . import config
from .knowledge_base import get_gemini_analysis_prompt

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5
_ANALYSIS_FIELDS = (
    "virality_score",
    "engagement_velocity",
    "trend_type",
    "virality_reason",
    "audio_lifecycle",
    "relevance_score",
    "recommended_campus",
)


def analyze_posts(
    posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> List[Dict[str, Any]]:
    """Score and rank posts using Gemini Flash-Lite analysis.

    Args:
        posts: Raw post dicts conforming to ``STANDARD_POST_KEYS``.
        test_mode: If ``True``, skip API calls and return deterministic
            mock scores derived from each post's ``post_id``.

    Returns:
        A list of enriched post dicts (original fields + analysis fields +
        ``composite_score``), sorted by ``composite_score`` descending,
        filtered by ``ANALYZER_MIN_SCORE``, and capped at ``ANALYZER_TOP_N``.
    """

    if test_mode or config.is_test_mode():
        return _mock_analyze(posts)

    if config._is_placeholder(config.GEMINI_API_KEY):
        logger.warning("GEMINI_API_KEY is missing or placeholder; skipping analysis.")
        return []

    system_prompt = get_gemini_analysis_prompt()
    enriched: List[Dict[str, Any]] = []
    api_calls = 0

    for i in range(0, len(posts), _BATCH_SIZE):
        if api_calls >= config.MAX_GEMINI_CALLS_PER_RUN:
            logger.warning(
                "Gemini API budget exhausted (%d calls); stopping analysis.",
                config.MAX_GEMINI_CALLS_PER_RUN,
            )
            break

        batch = posts[i : i + _BATCH_SIZE]
        batch_input = _format_batch(batch)

        try:
            response = requests.post(
                f"{config.GEMINI_API_ENDPOINT}?key={config.GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}],
                    },
                    "contents": [{"parts": [{"text": batch_input}]}],
                    "generationConfig": {
                        "temperature": config.GEMINI_ANALYSIS_TEMPERATURE,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=30,
            )
            api_calls += 1
        except requests.RequestException as exc:
            logger.error("Gemini API request failed: %s", exc)
            continue

        if response.status_code != 200:
            logger.error(
                "Gemini API returned %d: %s",
                response.status_code,
                response.text[:200],
            )
            continue

        analyses = _parse_gemini_response(response.text)
        _merge_analyses(batch, analyses, enriched)

    return _rank_and_filter(enriched)


def _format_batch(posts: List[Dict[str, Any]]) -> str:
    """Format a batch of posts as a JSON string for the Gemini prompt."""

    summaries = []
    for post in posts:
        summaries.append(
            {
                "post_id": post.get("post_id", ""),
                "platform": post.get("platform", ""),
                "caption": post.get("caption", ""),
                "hashtags": post.get("hashtags", []),
                "views": post.get("views", 0),
                "likes": post.get("likes", 0),
                "comments": post.get("comments", 0),
                "shares": post.get("shares", 0),
                "saves": post.get("saves", 0),
                "audio_name": post.get("audio_name", ""),
                "audio_author": post.get("audio_author", ""),
                "author_followers": post.get("author_followers", 0),
                "posted_at": post.get("posted_at", ""),
            }
        )
    return json.dumps(summaries, indent=2)


def _parse_gemini_response(raw_text: str) -> List[Dict[str, Any]]:
    """Extract a JSON array from Gemini's response text.

    Handles three shapes:
    1. Clean JSON array
    2. JSON wrapped in the Gemini API candidates structure
    3. JSON inside markdown code fences
    """

    # First try to parse as Gemini API response structure
    try:
        api_response = json.loads(raw_text)
        if isinstance(api_response, dict) and "candidates" in api_response:
            text = (
                api_response["candidates"][0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return _extract_json_array(text)
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    return _extract_json_array(raw_text)


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array from text, stripping code fences if present."""

    text = text.strip()

    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        logger.warning("Failed to parse Gemini JSON response: %.100s...", text)

    return []


def _merge_analyses(
    batch: List[Dict[str, Any]],
    analyses: List[Dict[str, Any]],
    enriched: List[Dict[str, Any]],
) -> None:
    """Merge Gemini analysis results back into the original post dicts."""

    analysis_by_id = {a.get("post_id"): a for a in analyses if a.get("post_id")}

    for post in batch:
        post_id = post.get("post_id", "")
        analysis = analysis_by_id.get(post_id, {})

        merged = dict(post)
        for field in _ANALYSIS_FIELDS:
            merged[field] = analysis.get(field, _default_for(field))

        virality = merged.get("virality_score", 0)
        relevance = merged.get("relevance_score", 0)
        if not isinstance(virality, (int, float)):
            virality = 0
        if not isinstance(relevance, (int, float)):
            relevance = 0
        merged["composite_score"] = round(virality * relevance / 100, 1)

        enriched.append(merged)


def _default_for(field: str) -> Any:
    """Return a sensible default for missing analysis fields."""

    if field in ("virality_score", "relevance_score"):
        return 0
    if field == "engagement_velocity":
        return "low"
    if field == "trend_type":
        return "format_driven"
    if field == "audio_lifecycle":
        return "no_audio"
    if field == "recommended_campus":
        return "both"
    return ""


def _rank_and_filter(enriched: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter by min score, sort descending, and cap at top N."""

    filtered = [
        post
        for post in enriched
        if post.get("composite_score", 0) >= config.ANALYZER_MIN_SCORE
    ]
    filtered.sort(key=lambda p: p.get("composite_score", 0), reverse=True)
    return filtered[: config.ANALYZER_TOP_N]


def _mock_analyze(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return deterministic mock analysis scores for test mode."""

    enriched: List[Dict[str, Any]] = []

    for post in posts:
        post_id = post.get("post_id", "unknown")
        seed = int(hashlib.md5(str(post_id).encode()).hexdigest()[:8], 16)

        virality = 50 + (seed % 51)  # 50-100
        relevance = 50 + ((seed >> 8) % 51)  # 50-100
        composite = round(virality * relevance / 100, 1)

        trend_types = ("macro_beauty", "campus_specific", "audio_driven", "format_driven")
        velocities = ("low", "medium", "high")
        lifecycles = ("emerging", "rising", "peak", "saturated", "no_audio")
        campuses = ("uofa", "calpoly", "both")

        merged = dict(post)
        merged.update(
            {
                "virality_score": virality,
                "engagement_velocity": velocities[seed % len(velocities)],
                "trend_type": trend_types[seed % len(trend_types)],
                "virality_reason": f"Mock analysis for {post_id}",
                "audio_lifecycle": lifecycles[seed % len(lifecycles)],
                "relevance_score": relevance,
                "recommended_campus": campuses[seed % len(campuses)],
                "composite_score": composite,
            }
        )
        enriched.append(merged)

    return _rank_and_filter(enriched)
