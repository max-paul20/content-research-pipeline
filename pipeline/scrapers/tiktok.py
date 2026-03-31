"""TikTok scraping entry point for the Unigliss content research pipeline."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import requests

from pipeline.config import RAPIDAPI_BASE_URL, RAPIDAPI_KEY, SCRAPE_LIMIT, SEEN_POSTS_FILE, TEST_MODE, TIKTOK_ENDPOINTS

from ._common import (
    HASHTAG_SEEDS,
    _API_KEY_PLACEHOLDERS,
    _is_missing_api_key,
    current_run_marker,
    dedupe_posts,
    extract_hashtags,
    extract_items,
    get_nested,
    is_relevant_post,
    load_seen_posts,
    normalize_timestamp,
    pick_first,
    request_json,
    safe_int,
    save_seen_posts,
    select_rotating_hashtags,
    utc_now_iso,
)

LOGGER = logging.getLogger(__name__)
PLATFORM = "tiktok"


def scrape_tiktok(test_mode: bool = False) -> List[Dict[str, Any]]:
    """Scrape TikTok discovery and hashtag feeds into the standardized schema."""

    if test_mode or TEST_MODE:
        return get_mock_posts()

    if _is_missing_api_key(RAPIDAPI_KEY):
        LOGGER.warning("TikTok scrape skipped: RAPIDAPI_KEY is missing or placeholder.")
        return []

    scraped_at = utc_now_iso()
    seen_posts = load_seen_posts(SEEN_POSTS_FILE, LOGGER)
    collected_posts: List[Dict[str, Any]] = []
    successful_endpoints = 0

    trending_payload = request_json(
        requests.get,
        platform=PLATFORM,
        endpoint_name="trending",
        base_url=RAPIDAPI_BASE_URL,
        endpoint=TIKTOK_ENDPOINTS["trending"],
        api_key=RAPIDAPI_KEY,
        params={"limit": SCRAPE_LIMIT},
        logger=LOGGER,
    )
    if trending_payload is not None:
        successful_endpoints += 1
        collected_posts.extend(_normalize_payload(trending_payload, scraped_at, "trending"))

    hashtags = _select_hashtags_for_run()
    per_hashtag_limit = max(1, min(5, SCRAPE_LIMIT))
    for hashtag in hashtags:
        hashtag_payload = request_json(
            requests.get,
            platform=PLATFORM,
            endpoint_name=f"hashtag:{hashtag}",
            base_url=RAPIDAPI_BASE_URL,
            endpoint=TIKTOK_ENDPOINTS["hashtag"],
            api_key=RAPIDAPI_KEY,
            params={"name": hashtag, "limit": per_hashtag_limit},
            logger=LOGGER,
        )
        if hashtag_payload is None:
            continue
        successful_endpoints += 1
        collected_posts.extend(_normalize_payload(hashtag_payload, scraped_at, f"hashtag:{hashtag}"))

    if successful_endpoints == 0:
        LOGGER.warning("All TikTok endpoints failed this run.")
        return []

    new_posts = _dedupe_posts(collected_posts, seen_posts)
    save_seen_posts(SEEN_POSTS_FILE, seen_posts, LOGGER)
    return new_posts


def get_mock_posts() -> List[Dict[str, Any]]:
    """Return realistic fake TikTok posts for test runs."""

    scraped_at = utc_now_iso()
    return [
        {
            "post_id": "tk_001",
            "platform": PLATFORM,
            "author": "desertnaildiary",
            "author_followers": 18400,
            "caption": "POV: your rush week nails have to match every outfit #nailtok #rushweek #uofa",
            "hashtags": ["nailtok", "rushweek", "uofa"],
            "views": 182400,
            "likes": 21900,
            "comments": 420,
            "shares": 1860,
            "saves": 2240,
            "url": "https://www.tiktok.com/@desertnaildiary/video/tk_001",
            "audio_name": "original sound - campus glam check",
            "audio_author": "desertnaildiary",
            "posted_at": "2026-03-30T23:15:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "rush-week-nails"},
        },
        {
            "post_id": "tk_002",
            "platform": PLATFORM,
            "author": "slobeautyrun",
            "author_followers": 9200,
            "caption": "GRWM for a Higuera coffee run before class #grwm #calpoly #collegeaesthetic",
            "hashtags": ["grwm", "calpoly", "collegeaesthetic"],
            "views": 96400,
            "likes": 11100,
            "comments": 148,
            "shares": 1260,
            "saves": 1720,
            "url": "https://www.tiktok.com/@slobeautyrun/video/tk_002",
            "audio_name": "late spring reel flip",
            "audio_author": "trendhopper",
            "posted_at": "2026-03-30T21:05:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "calpoly-grwm"},
        },
        {
            "post_id": "tk_003",
            "platform": PLATFORM,
            "author": "lashlabwildcats",
            "author_followers": 12600,
            "caption": "Watch this lash fill go from 0 to game day ready #lashtok #beardown #tutorial",
            "hashtags": ["lashtok", "beardown", "tutorial"],
            "views": 141800,
            "likes": 16400,
            "comments": 236,
            "shares": 1530,
            "saves": 2060,
            "url": "https://www.tiktok.com/@lashlabwildcats/video/tk_003",
            "audio_name": "beat switch reveal",
            "audio_author": "nightdriveaudio",
            "posted_at": "2026-03-30T19:40:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "lash-fill"},
        },
        {
            "post_id": "tk_004",
            "platform": PLATFORM,
            "author": "mustangmanis",
            "author_followers": 7300,
            "caption": "How I do clean-girl chrome for Cal Poly girls who still want a little extra #nailart #calpolyslo #beautytok",
            "hashtags": ["nailart", "calpolyslo", "beautytok"],
            "views": 78400,
            "likes": 8800,
            "comments": 102,
            "shares": 970,
            "saves": 1430,
            "url": "https://www.tiktok.com/@mustangmanis/video/tk_004",
            "audio_name": "soft synth reset",
            "audio_author": "coastalcuts",
            "posted_at": "2026-03-30T18:20:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "clean-girl-nails"},
        },
        {
            "post_id": "tk_005",
            "platform": PLATFORM,
            "author": "dormvanitycheck",
            "author_followers": 15600,
            "caption": "Dorm room setup but make it beauty-creator functional #dormlife #beautyhacks #dayinmylife",
            "hashtags": ["dormlife", "beautyhacks", "dayinmylife"],
            "views": 118300,
            "likes": 13600,
            "comments": 188,
            "shares": 1490,
            "saves": 1930,
            "url": "https://www.tiktok.com/@dormvanitycheck/video/tk_005",
            "audio_name": "original sound - desk reset",
            "audio_author": "dormvanitycheck",
            "posted_at": "2026-03-30T17:10:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "dorm-beauty-setup"},
        },
        {
            "post_id": "tk_006",
            "platform": PLATFORM,
            "author": "uagamedayglam",
            "author_followers": 20400,
            "caption": "The 15 second game day makeup transition that always loops #makeuptutorial #wildcats #transformation",
            "hashtags": ["makeuptutorial", "wildcats", "transformation"],
            "views": 203100,
            "likes": 24600,
            "comments": 392,
            "shares": 2410,
            "saves": 2780,
            "url": "https://www.tiktok.com/@uagamedayglam/video/tk_006",
            "audio_name": "stadium lights",
            "audio_author": "sidelineedits",
            "posted_at": "2026-03-30T16:45:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "game-day-makeup"},
        },
    ]


def _select_hashtags_for_run(run_marker: Optional[int] = None, batch_size: int = 9) -> List[str]:
    """Return the TikTok hashtag slice for the current run window."""

    marker = run_marker if run_marker is not None else current_run_marker()
    return select_rotating_hashtags(marker, batch_size=batch_size)


def _dedupe_posts(
    posts: Sequence[Dict[str, Any]],
    seen_posts: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply standardized dedup logic for TikTok posts."""

    return dedupe_posts(posts, seen_posts, platform=PLATFORM, logger=LOGGER)


def _normalize_payload(payload: Any, scraped_at: str, source_label: str) -> List[Dict[str, Any]]:
    """Normalize a variable TikTok payload into standardized post dictionaries."""

    items = extract_items(payload)
    if not items:
        LOGGER.info("TikTok endpoint %s returned zero results.", source_label)
        return []

    normalized: List[Dict[str, Any]] = []
    for item in items:
        post = _normalize_post(item, scraped_at)
        if post is None:
            LOGGER.warning("TikTok returned a malformed post for %s; skipping item.", source_label)
            continue
        if is_relevant_post(post["caption"], post["hashtags"]):
            normalized.append(post)
    return normalized


def _normalize_post(raw_post: Dict[str, Any], scraped_at: str) -> Optional[Dict[str, Any]]:
    """Convert a TikTok API item into the analyzer-facing schema."""

    post_id = str(
        pick_first(
            raw_post.get("aweme_id"),
            raw_post.get("id"),
            raw_post.get("post_id"),
            default="",
        )
    ).strip()
    if not post_id:
        return None

    author = str(
        pick_first(
            get_nested(raw_post, "author", "unique_id"),
            get_nested(raw_post, "author", "username"),
            get_nested(raw_post, "author", "nickname"),
            get_nested(raw_post, "authorInfo", "uniqueId"),
            get_nested(raw_post, "authorInfo", "userName"),
            raw_post.get("author_name"),
            default="",
        )
    ).strip()
    caption = str(
        pick_first(
            raw_post.get("desc"),
            raw_post.get("caption"),
            raw_post.get("text"),
            default="",
        )
    ).strip()
    hashtags = _extract_tiktok_hashtags(raw_post, caption)
    url = str(
        pick_first(
            raw_post.get("share_url"),
            raw_post.get("url"),
            raw_post.get("shareUrl"),
            get_nested(raw_post, "video", "share_url"),
            default="",
        )
    ).strip()
    if not url and author:
        url = f"https://www.tiktok.com/@{author}/video/{post_id}"

    return {
        "post_id": post_id,
        "platform": PLATFORM,
        "author": author,
        "author_followers": safe_int(
            pick_first(
                get_nested(raw_post, "author", "follower_count"),
                get_nested(raw_post, "author", "followers"),
                get_nested(raw_post, "authorStats", "followerCount"),
                get_nested(raw_post, "authorStats", "followers"),
                get_nested(raw_post, "authorInfo", "followerCount"),
                raw_post.get("author_followers"),
            )
        ),
        "caption": caption,
        "hashtags": hashtags,
        "views": safe_int(
            pick_first(
                get_nested(raw_post, "stats", "play_count"),
                get_nested(raw_post, "statistics", "play_count"),
                get_nested(raw_post, "statistics", "viewCount"),
                raw_post.get("view_count"),
                raw_post.get("views"),
            )
        ),
        "likes": safe_int(
            pick_first(
                get_nested(raw_post, "stats", "digg_count"),
                get_nested(raw_post, "statistics", "digg_count"),
                get_nested(raw_post, "statistics", "likeCount"),
                raw_post.get("like_count"),
                raw_post.get("likes"),
            )
        ),
        "comments": safe_int(
            pick_first(
                get_nested(raw_post, "stats", "comment_count"),
                get_nested(raw_post, "statistics", "comment_count"),
                get_nested(raw_post, "statistics", "commentCount"),
                raw_post.get("comment_count"),
                raw_post.get("comments"),
            )
        ),
        "shares": safe_int(
            pick_first(
                get_nested(raw_post, "stats", "share_count"),
                get_nested(raw_post, "statistics", "share_count"),
                get_nested(raw_post, "statistics", "shareCount"),
                raw_post.get("share_count"),
                raw_post.get("shares"),
            )
        ),
        "saves": safe_int(
            pick_first(
                get_nested(raw_post, "stats", "collect_count"),
                get_nested(raw_post, "statistics", "collect_count"),
                get_nested(raw_post, "statistics", "collectCount"),
                raw_post.get("save_count"),
                raw_post.get("saves"),
            )
        ),
        "url": url,
        "audio_name": pick_first(
            get_nested(raw_post, "music", "title"),
            get_nested(raw_post, "music", "name"),
            get_nested(raw_post, "music_info", "title"),
            raw_post.get("audio_name"),
            default=None,
        ),
        "audio_author": pick_first(
            get_nested(raw_post, "music", "authorName"),
            get_nested(raw_post, "music", "author"),
            get_nested(raw_post, "music_info", "author"),
            raw_post.get("audio_author"),
            default=None,
        ),
        "posted_at": normalize_timestamp(
            pick_first(
                raw_post.get("create_time"),
                raw_post.get("createTime"),
                raw_post.get("timestamp"),
                raw_post.get("posted_at"),
                default=None,
            )
        ),
        "scraped_at": scraped_at,
        "raw_data": raw_post,
    }


def _extract_tiktok_hashtags(raw_post: Dict[str, Any], caption: str) -> List[str]:
    """Collect hashtags from TikTok caption text and text-metadata blocks."""

    hashtags = extract_hashtags(caption)
    text_extra = raw_post.get("textExtra") or raw_post.get("text_extra") or []
    extra_tags: List[str] = []
    for item in text_extra:
        if not isinstance(item, dict):
            continue
        tag = pick_first(
            item.get("hashtagName"),
            item.get("hashtag_name"),
            item.get("tag_name"),
            default="",
        )
        if tag:
            extra_tags.append(str(tag).lower())
    return list(dict.fromkeys(hashtags + extra_tags))


__all__ = ["HASHTAG_SEEDS", "get_mock_posts", "scrape_tiktok"]
