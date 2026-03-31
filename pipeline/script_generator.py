"""Tier 2 creative brief generation via Claude Sonnet.

Takes the top-ranked posts from the analyzer, splits them by campus, and
generates lean creative briefs using the Anthropic Messages API.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import requests

from . import config
from .knowledge_base import get_sonnet_script_prompt
from .scrapers._common import utc_now_iso

logger = logging.getLogger(__name__)


def generate_scripts(
    analyzed_posts: List[Dict[str, Any]],
    test_mode: bool = False,
) -> List[Dict[str, Any]]:
    """Generate campus-specific creative briefs from analyzed posts.

    Args:
        analyzed_posts: Enriched post dicts from the analyzer, each containing
            ``recommended_campus``, ``composite_score``, and analysis fields.
        test_mode: If ``True``, skip API calls and return mock briefs.

    Returns:
        A list of script dicts, each containing ``campus``, ``trend_type``,
        ``brief``, ``source_url``, and ``generated_at``.
    """

    if test_mode or config.is_test_mode():
        return _mock_generate(analyzed_posts)

    if config._is_placeholder(config.ANTHROPIC_API_KEY):
        logger.warning("ANTHROPIC_API_KEY is missing or placeholder; skipping generation.")
        return []

    arizona, calpoly = _split_by_campus(analyzed_posts)
    scripts: List[Dict[str, Any]] = []

    # Arizona batch first
    for post in arizona[: config.SCRIPTS_PER_CAMPUS]:
        script = _generate_one(post, "uofa")
        if script:
            scripts.append(script)

    # Cal Poly batch second
    for post in calpoly[: config.SCRIPTS_PER_CAMPUS]:
        script = _generate_one(post, "calpoly")
        if script:
            scripts.append(script)

    return scripts


def _split_by_campus(
    posts: List[Dict[str, Any]],
) -> tuple:
    """Split posts into Arizona and Cal Poly buckets.

    Posts with ``recommended_campus="both"`` go into both buckets.
    Each bucket is sorted by ``composite_score`` descending.
    """

    arizona: List[Dict[str, Any]] = []
    calpoly: List[Dict[str, Any]] = []

    for post in posts:
        campus = post.get("recommended_campus", "both")
        if campus in ("uofa", "both"):
            arizona.append(post)
        if campus in ("calpoly", "both"):
            calpoly.append(post)

    arizona.sort(key=lambda p: p.get("composite_score", 0), reverse=True)
    calpoly.sort(key=lambda p: p.get("composite_score", 0), reverse=True)

    return arizona, calpoly


def _generate_one(post: Dict[str, Any], campus: str) -> Dict[str, Any] | None:
    """Call Sonnet to generate a single creative brief."""

    system_prompt = get_sonnet_script_prompt(campus)
    user_prompt = _build_user_prompt(post)

    try:
        response = requests.post(
            config.ANTHROPIC_API_URL,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.ANTHROPIC_MODEL,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        logger.error("Anthropic API request failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.error(
            "Anthropic API returned %d: %s",
            response.status_code,
            response.text[:200],
        )
        return None

    brief = _extract_brief(response.text)
    if not brief:
        return None

    return {
        "campus": campus,
        "trend_type": post.get("trend_type", ""),
        "brief": brief,
        "source_url": post.get("url", ""),
        "generated_at": utc_now_iso(),
    }


def _build_user_prompt(post: Dict[str, Any]) -> str:
    """Format a post and its analysis into a user-turn prompt for Sonnet."""

    parts = [
        "Generate ONE lean creative brief for this viral trend:\n",
        f"Platform: {post.get('platform', 'unknown')}",
        f"Caption: {post.get('caption', '')}",
        f"Hashtags: {', '.join(post.get('hashtags', []))}",
        f"Views: {post.get('views', 0):,}",
        f"Likes: {post.get('likes', 0):,}",
        f"Comments: {post.get('comments', 0):,}",
        f"Shares: {post.get('shares', 0):,}",
        f"Saves: {post.get('saves', 0):,}",
        f"Audio: {post.get('audio_name', 'none')} by {post.get('audio_author', 'unknown')}",
        "",
        "Gemini Analysis:",
        f"  Virality Score: {post.get('virality_score', 0)}/100",
        f"  Trend Type: {post.get('trend_type', 'unknown')}",
        f"  Virality Reason: {post.get('virality_reason', '')}",
        f"  Audio Lifecycle: {post.get('audio_lifecycle', 'unknown')}",
        f"  Engagement Velocity: {post.get('engagement_velocity', 'unknown')}",
    ]
    return "\n".join(parts)


def _extract_brief(raw_text: str) -> str:
    """Extract the brief text from an Anthropic API response."""

    try:
        data = json.loads(raw_text)
        if isinstance(data, dict) and "content" in data:
            for block in data["content"]:
                if block.get("type") == "text":
                    return block.get("text", "").strip()
    except (json.JSONDecodeError, KeyError):
        logger.warning("Failed to parse Anthropic response: %.100s...", raw_text)

    return ""


def _mock_generate(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return mock briefs for test mode."""

    arizona, calpoly = _split_by_campus(posts)
    scripts: List[Dict[str, Any]] = []

    campus_emoji = {"uofa": "\U0001f335", "calpoly": "\U0001f40e"}
    campus_names = {"uofa": "Arizona", "calpoly": "Cal Poly"}
    campus_spots = {
        "uofa": ["Old Main", "4th Ave", "Arizona Stadium"],
        "calpoly": ["Higuera St", "Bishop Peak", "Dexter Lawn"],
    }

    for campus_key, bucket in [("uofa", arizona), ("calpoly", calpoly)]:
        for post in bucket[: config.SCRIPTS_PER_CAMPUS]:
            spot = campus_spots[campus_key][len(scripts) % len(campus_spots[campus_key])]
            scripts.append(
                {
                    "campus": campus_key,
                    "trend_type": post.get("trend_type", "format_driven"),
                    "brief": (
                        f"{campus_emoji[campus_key]} HOOK: POV you just discovered "
                        f"the best beauty hack at {spot}\n"
                        f"\U0001f4dd KEY BEATS:\n"
                        f"- Quick before/after at {spot}\n"
                        f"- Show the product close-up\n"
                        f"- Friend reaction shot\n"
                        f"\U0001f5e3\ufe0f DIALOGUE: 'I found her on Unigliss btw'\n"
                        f"\U0001f3b5 AUDIO: {post.get('audio_name', 'trending sound')}\n"
                        f"#\ufe0f\u20e3 HASHTAGS: #beauty #{campus_names[campus_key].lower()} "
                        f"#unigliss #grwm\n"
                        f"\U0001f4cd CAMPUS TIE-IN: {spot}"
                    ),
                    "source_url": post.get("url", ""),
                    "generated_at": utc_now_iso(),
                }
            )

    return scripts
