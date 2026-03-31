"""Instagram scraping entry point for the Unigliss content research pipeline."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import requests

from pipeline.config import (
    INSTAGRAM_ENDPOINTS,
    RAPIDAPI_BASE_URL,
    RAPIDAPI_KEY,
    SCRAPE_LIMIT,
    SEEN_POSTS_FILE,
    TEST_MODE,
)

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
PLATFORM = "instagram"


def scrape_instagram(test_mode: bool = False) -> List[Dict[str, Any]]:
    """Scrape Instagram Reels and hashtag feeds into the standardized schema."""

    if test_mode or TEST_MODE:
        return get_mock_posts()

    if _is_missing_api_key(RAPIDAPI_KEY):
        LOGGER.warning("Instagram scrape skipped: RAPIDAPI_KEY is missing or placeholder.")
        return []

    scraped_at = utc_now_iso()
    seen_posts = load_seen_posts(SEEN_POSTS_FILE, LOGGER)
    collected_posts: List[Dict[str, Any]] = []
    successful_endpoints = 0

    reels_payload = request_json(
        requests.get,
        platform=PLATFORM,
        endpoint_name="reels",
        base_url=RAPIDAPI_BASE_URL,
        endpoint=INSTAGRAM_ENDPOINTS["reels"],
        api_key=RAPIDAPI_KEY,
        params={"limit": SCRAPE_LIMIT},
        logger=LOGGER,
    )
    if reels_payload is not None:
        successful_endpoints += 1
        collected_posts.extend(_normalize_payload(reels_payload, scraped_at, "reels"))

    hashtags = _select_hashtags_for_run()
    per_hashtag_limit = max(1, min(5, SCRAPE_LIMIT))
    for hashtag in hashtags:
        hashtag_payload = request_json(
            requests.get,
            platform=PLATFORM,
            endpoint_name=f"hashtag:{hashtag}",
            base_url=RAPIDAPI_BASE_URL,
            endpoint=INSTAGRAM_ENDPOINTS["hashtag"],
            api_key=RAPIDAPI_KEY,
            params={"name": hashtag, "limit": per_hashtag_limit},
            logger=LOGGER,
        )
        if hashtag_payload is None:
            continue
        successful_endpoints += 1
        collected_posts.extend(_normalize_payload(hashtag_payload, scraped_at, f"hashtag:{hashtag}"))

    if successful_endpoints == 0:
        LOGGER.warning("All Instagram endpoints failed this run.")
        return []

    new_posts = _dedupe_posts(collected_posts, seen_posts)
    save_seen_posts(SEEN_POSTS_FILE, seen_posts, LOGGER)
    return new_posts


def get_mock_posts() -> List[Dict[str, Any]]:
    """Return realistic fake Instagram posts for test runs."""

    scraped_at = utc_now_iso()
    return [
        {
            "post_id": "ig_001",
            "platform": PLATFORM,
            "author": "uniglisswildcatlooks",
            "author_followers": 14300,
            "caption": "Desert heat-proof makeup that still survives a walk through campus #uofa #collegemakeup #reels",
            "hashtags": ["uofa", "collegemakeup", "reels"],
            "views": 86400,
            "likes": 9200,
            "comments": 164,
            "shares": 0,
            "saves": 1410,
            "url": "https://www.instagram.com/reel/ig_001/",
            "audio_name": "soft summer switch",
            "audio_author": "trendrelay",
            "posted_at": "2026-03-30T22:00:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "heat-proof-makeup"},
        },
        {
            "post_id": "ig_002",
            "platform": PLATFORM,
            "author": "slobeautynotes",
            "author_followers": 8700,
            "caption": "A Bishop Peak-friendly beauty reset that still looks cute in class #calpoly #skincareroutine #dayinmylife",
            "hashtags": ["calpoly", "skincareroutine", "dayinmylife"],
            "views": 52200,
            "likes": 6400,
            "comments": 76,
            "shares": 0,
            "saves": 980,
            "url": "https://www.instagram.com/reel/ig_002/",
            "audio_name": "coastal slow build",
            "audio_author": "morningsignal",
            "posted_at": "2026-03-30T20:25:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "campus-reset"},
        },
        {
            "post_id": "ig_003",
            "platform": PLATFORM,
            "author": "rushreadybeauty",
            "author_followers": 11600,
            "caption": "Bid day hair ideas that don't wilt by noon #rushweek #hairtok #sorority",
            "hashtags": ["rushweek", "hairtok", "sorority"],
            "views": 74300,
            "likes": 8100,
            "comments": 112,
            "shares": 0,
            "saves": 1320,
            "url": "https://www.instagram.com/reel/ig_003/",
            "audio_name": "late bloom chorus",
            "audio_author": "trendgarden",
            "posted_at": "2026-03-30T19:30:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "bid-day-hair"},
        },
        {
            "post_id": "ig_004",
            "platform": PLATFORM,
            "author": "mustanglashclub",
            "author_followers": 6900,
            "caption": "How I make lash fills look soft enough for class and dinner on Higuera #lashtok #calpolyslo #tutorial",
            "hashtags": ["lashtok", "calpolyslo", "tutorial"],
            "views": 48800,
            "likes": 5700,
            "comments": 64,
            "shares": 0,
            "saves": 890,
            "url": "https://www.instagram.com/reel/ig_004/",
            "audio_name": "clean outro",
            "audio_author": "reelrelay",
            "posted_at": "2026-03-30T18:45:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "lash-fill"},
        },
        {
            "post_id": "ig_005",
            "platform": PLATFORM,
            "author": "oldmainglam",
            "author_followers": 13200,
            "caption": "Old Main photo-day nails that still look good close up #nailart #uarizona #beforeandafter",
            "hashtags": ["nailart", "uarizona", "beforeandafter"],
            "views": 91500,
            "likes": 10100,
            "comments": 154,
            "shares": 0,
            "saves": 1670,
            "url": "https://www.instagram.com/reel/ig_005/",
            "audio_name": "flash frame build",
            "audio_author": "loopdistrict",
            "posted_at": "2026-03-30T17:35:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "photo-day-nails"},
        },
        {
            "post_id": "ig_006",
            "platform": PLATFORM,
            "author": "dormskinreset",
            "author_followers": 9800,
            "caption": "The dorm skincare shelf that actually survives finals week #dormlife #beautytok #campuslife",
            "hashtags": ["dormlife", "beautytok", "campuslife"],
            "views": 55200,
            "likes": 6200,
            "comments": 81,
            "shares": 0,
            "saves": 1110,
            "url": "https://www.instagram.com/reel/ig_006/",
            "audio_name": "ambient morning glass",
            "audio_author": "quietcuts",
            "posted_at": "2026-03-30T16:50:00Z",
            "scraped_at": scraped_at,
            "raw_data": {"mock": True, "theme": "dorm-skincare"},
        },
    ]


def _select_hashtags_for_run(run_marker: Optional[int] = None, batch_size: int = 9) -> List[str]:
    """Return the Instagram hashtag slice for the current run window."""

    marker = run_marker if run_marker is not None else current_run_marker()
    return select_rotating_hashtags(marker, batch_size=batch_size)


def _dedupe_posts(
    posts: Sequence[Dict[str, Any]],
    seen_posts: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply standardized dedup logic for Instagram posts."""

    return dedupe_posts(posts, seen_posts, platform=PLATFORM, logger=LOGGER)


def _normalize_payload(payload: Any, scraped_at: str, source_label: str) -> List[Dict[str, Any]]:
    """Normalize a variable Instagram payload into standardized post dictionaries."""

    items = extract_items(payload)
    if not items:
        LOGGER.info("Instagram endpoint %s returned zero results.", source_label)
        return []

    normalized: List[Dict[str, Any]] = []
    for item in items:
        post = _normalize_post(item, scraped_at)
        if post is None:
            LOGGER.warning("Instagram returned a malformed post for %s; skipping item.", source_label)
            continue
        if is_relevant_post(post["caption"], post["hashtags"]):
            normalized.append(post)
    return normalized


def _normalize_post(raw_post: Dict[str, Any], scraped_at: str) -> Optional[Dict[str, Any]]:
    """Convert an Instagram API item into the analyzer-facing schema."""

    post_id = str(
        pick_first(
            raw_post.get("id"),
            raw_post.get("pk"),
            raw_post.get("media_id"),
            raw_post.get("code"),
            default="",
        )
    ).strip()
    if not post_id:
        return None

    author = str(
        pick_first(
            get_nested(raw_post, "user", "username"),
            get_nested(raw_post, "owner", "username"),
            get_nested(raw_post, "author", "username"),
            raw_post.get("username"),
            default="",
        )
    ).strip()
    caption = str(
        pick_first(
            get_nested(raw_post, "caption", "text"),
            raw_post.get("caption_text"),
            raw_post.get("caption"),
            raw_post.get("text"),
            raw_post.get("description"),
            default="",
        )
    ).strip()
    hashtags = _extract_instagram_hashtags(raw_post, caption)
    shortcode = str(pick_first(raw_post.get("code"), raw_post.get("shortcode"), default="")).strip()
    url = str(
        pick_first(
            raw_post.get("permalink"),
            raw_post.get("url"),
            raw_post.get("link"),
            get_nested(raw_post, "share", "link"),
            default="",
        )
    ).strip()
    if not url and shortcode:
        url = f"https://www.instagram.com/reel/{shortcode}/"

    return {
        "post_id": post_id,
        "platform": PLATFORM,
        "author": author,
        "author_followers": safe_int(
            pick_first(
                get_nested(raw_post, "user", "follower_count"),
                get_nested(raw_post, "user", "followers"),
                get_nested(raw_post, "owner", "follower_count"),
                get_nested(raw_post, "author", "follower_count"),
                raw_post.get("author_followers"),
            )
        ),
        "caption": caption,
        "hashtags": hashtags,
        "views": safe_int(
            pick_first(
                raw_post.get("play_count"),
                raw_post.get("view_count"),
                raw_post.get("video_view_count"),
                raw_post.get("views"),
            )
        ),
        "likes": safe_int(
            pick_first(
                raw_post.get("like_count"),
                raw_post.get("likes"),
                get_nested(raw_post, "edge_media_preview_like", "count"),
            )
        ),
        "comments": safe_int(
            pick_first(
                raw_post.get("comment_count"),
                raw_post.get("comments"),
                get_nested(raw_post, "edge_media_to_comment", "count"),
            )
        ),
        "shares": safe_int(
            pick_first(
                raw_post.get("share_count"),
                raw_post.get("reshare_count"),
                default=0,
            )
        ),
        "saves": safe_int(
            pick_first(
                raw_post.get("save_count"),
                raw_post.get("saved_count"),
                raw_post.get("saves"),
                default=0,
            )
        ),
        "url": url,
        "audio_name": pick_first(
            get_nested(raw_post, "clips_music_attribution_info", "song_name"),
            get_nested(raw_post, "music", "title"),
            raw_post.get("audio_name"),
            default=None,
        ),
        "audio_author": pick_first(
            get_nested(raw_post, "clips_music_attribution_info", "artist_name"),
            get_nested(raw_post, "music", "artist"),
            raw_post.get("audio_author"),
            default=None,
        ),
        "posted_at": normalize_timestamp(
            pick_first(
                raw_post.get("taken_at"),
                raw_post.get("timestamp"),
                raw_post.get("posted_at"),
                default=None,
            )
        ),
        "scraped_at": scraped_at,
        "raw_data": raw_post,
    }


def _extract_instagram_hashtags(raw_post: Dict[str, Any], caption: str) -> List[str]:
    """Collect hashtags from Instagram caption text and metadata blocks."""

    hashtags = extract_hashtags(caption)
    metadata_tags: List[str] = []
    inline_tags = raw_post.get("hashtags") or raw_post.get("tags") or []
    if isinstance(inline_tags, list):
        for tag in inline_tags:
            if isinstance(tag, str):
                metadata_tags.append(tag.lower().lstrip("#"))
            elif isinstance(tag, dict):
                value = pick_first(tag.get("name"), tag.get("tag"), default="")
                if value:
                    metadata_tags.append(str(value).lower().lstrip("#"))
    return list(dict.fromkeys(hashtags + metadata_tags))


__all__ = ["HASHTAG_SEEDS", "get_mock_posts", "scrape_instagram"]
