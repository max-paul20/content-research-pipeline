"""Unit tests for the TikTok and Instagram scraper modules."""

import json
import logging
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import requests

import pipeline.config as config
from pipeline.scrapers import get_mock_instagram_posts, get_mock_tiktok_posts, scrape_instagram, scrape_tiktok
from pipeline.scrapers import instagram, tiktok
from pipeline.scrapers._common import (
    STANDARD_POST_KEYS,
    extract_items,
    flatten_hashtag_seeds,
    load_seen_posts,
    normalize_timestamp,
    safe_int,
    save_seen_posts,
    select_rotating_hashtags,
)


class ScraperTests(unittest.TestCase):
    """Verify standardized schemas, rotation, dedup, and error handling."""

    def test_mock_posts_match_standardized_schema(self) -> None:
        for factory in (get_mock_tiktok_posts, get_mock_instagram_posts):
            posts = factory()
            self.assertGreaterEqual(len(posts), 5)
            self.assertLessEqual(len(posts), 8)
            for post in posts:
                self.assertEqual(tuple(post.keys()), STANDARD_POST_KEYS)
                self.assertIsInstance(post["post_id"], str)
                self.assertIsInstance(post["platform"], str)
                self.assertIsInstance(post["author"], str)
                self.assertIsInstance(post["author_followers"], int)
                self.assertIsInstance(post["caption"], str)
                self.assertIsInstance(post["hashtags"], list)
                self.assertTrue(all(isinstance(tag, str) for tag in post["hashtags"]))
                self.assertIsInstance(post["views"], int)
                self.assertIsInstance(post["likes"], int)
                self.assertIsInstance(post["comments"], int)
                self.assertIsInstance(post["shares"], int)
                self.assertIsInstance(post["saves"], int)
                self.assertIsInstance(post["url"], str)
                self.assertTrue(post["audio_name"] is None or isinstance(post["audio_name"], str))
                self.assertTrue(post["audio_author"] is None or isinstance(post["audio_author"], str))
                self.assertTrue(post["posted_at"] is None or isinstance(post["posted_at"], str))
                self.assertIsInstance(post["scraped_at"], str)
                self.assertIsInstance(post["raw_data"], dict)

    def test_mock_posts_have_iso_timestamps(self) -> None:
        """All non-None posted_at and all scraped_at values must use Z-suffix ISO 8601."""
        for factory in (get_mock_tiktok_posts, get_mock_instagram_posts):
            for post in factory():
                self.assertTrue(
                    post["scraped_at"].endswith("Z"),
                    msg=f"scraped_at {post['scraped_at']!r} does not end with Z",
                )
                if post["posted_at"] is not None:
                    self.assertTrue(
                        post["posted_at"].endswith("Z"),
                        msg=f"posted_at {post['posted_at']!r} does not end with Z",
                    )

    def test_hashtag_rotation_logic_changes_across_runs(self) -> None:
        first_tiktok = tiktok._select_hashtags_for_run(run_marker=0, batch_size=9)
        second_tiktok = tiktok._select_hashtags_for_run(run_marker=1, batch_size=9)
        first_instagram = instagram._select_hashtags_for_run(run_marker=0, batch_size=9)
        second_instagram = instagram._select_hashtags_for_run(run_marker=1, batch_size=9)

        self.assertNotEqual(first_tiktok, second_tiktok)
        self.assertNotEqual(first_instagram, second_instagram)
        self.assertEqual(len(first_tiktok), 9)
        self.assertEqual(len(first_instagram), 9)

    def test_hashtag_rotation_covers_all_hashtags_over_full_period(self) -> None:
        """Every hashtag must appear in at least one batch window across the full period."""
        all_hashtags = set(flatten_hashtag_seeds())
        total = len(all_hashtags)
        batch_size = 9
        covered: set = set()
        # The period after which the rotation fully wraps is at most total runs
        for marker in range(total * 2):
            covered.update(select_rotating_hashtags(marker, batch_size=batch_size))
        self.assertEqual(
            covered,
            all_hashtags,
            msg=f"Tags never covered: {all_hashtags - covered}",
        )

    def test_dedup_skips_known_post_and_logs_it(self) -> None:
        seen_posts = {
            "tiktok_existing123": {
                "first_seen": "2026-03-31T10:00:00Z",
                "last_seen": "2026-03-31T10:00:00Z",
                "views_first_seen": 50000,
                "views_last_seen": 50000,
                "times_seen": 1,
                "platform": "tiktok",
            }
        }
        duplicate_post = {
            "post_id": "existing123",
            "platform": "tiktok",
            "author": "repeatcreator",
            "author_followers": 1000,
            "caption": "Repeat post",
            "hashtags": ["nailtok"],
            "views": 75000,
            "likes": 1000,
            "comments": 50,
            "shares": 40,
            "saves": 20,
            "url": "https://www.tiktok.com/@repeatcreator/video/existing123",
            "audio_name": None,
            "audio_author": None,
            "posted_at": None,
            "scraped_at": "2026-03-31T16:00:00Z",
            "raw_data": {},
        }

        with self.assertLogs("pipeline.scrapers.tiktok", level="INFO") as captured:
            new_posts = tiktok._dedupe_posts([duplicate_post], seen_posts)

        self.assertEqual(new_posts, [])
        self.assertIn("DEDUP: post existing123 seen before", "\n".join(captured.output))
        self.assertEqual(seen_posts["tiktok_existing123"]["views_last_seen"], 75000)
        self.assertEqual(seen_posts["tiktok_existing123"]["times_seen"], 2)

    def test_dedup_adds_new_post_to_seen_posts(self) -> None:
        seen_posts = {}
        new_post = {
            "post_id": "brandnew456",
            "platform": "instagram",
            "author": "newcreator",
            "author_followers": 2200,
            "caption": "Fresh reel",
            "hashtags": ["calpoly"],
            "views": 9100,
            "likes": 740,
            "comments": 22,
            "shares": 0,
            "saves": 88,
            "url": "https://www.instagram.com/reel/brandnew456/",
            "audio_name": None,
            "audio_author": None,
            "posted_at": None,
            "scraped_at": "2026-03-31T16:00:00Z",
            "raw_data": {},
        }

        new_posts = instagram._dedupe_posts([new_post], seen_posts)

        self.assertEqual(new_posts, [new_post])
        self.assertIn("instagram_brandnew456", seen_posts)
        self.assertEqual(seen_posts["instagram_brandnew456"]["views_first_seen"], 9100)
        self.assertEqual(seen_posts["instagram_brandnew456"]["times_seen"], 1)

    def test_dedup_skips_item_with_missing_post_id(self) -> None:
        """Posts without a post_id must be silently skipped (no crash, no entry added)."""
        seen_posts = {}
        malformed = {
            "post_id": "",
            "platform": "tiktok",
            "views": 1000,
            "scraped_at": "2026-03-31T16:00:00Z",
        }
        with self.assertLogs("pipeline.scrapers.tiktok", level="WARNING") as captured:
            result = tiktok._dedupe_posts([malformed], seen_posts)
        self.assertEqual(result, [])
        self.assertEqual(seen_posts, {})
        self.assertTrue(any("missing post_id" in line for line in captured.output))

    def test_failed_api_call_returns_empty_list_for_tiktok(self) -> None:
        with TemporaryDirectory() as temp_dir:
            seen_file = Path(temp_dir) / "seen_posts.json"
            with patch.object(tiktok, "RAPIDAPI_KEY", "real-key"), patch.object(
                tiktok, "SEEN_POSTS_FILE", seen_file
            ), patch("pipeline.scrapers.tiktok.requests.get", side_effect=requests.RequestException("boom")):
                posts = scrape_tiktok(test_mode=False)

        self.assertEqual(posts, [])

    def test_failed_api_call_returns_empty_list_for_instagram(self) -> None:
        with TemporaryDirectory() as temp_dir:
            seen_file = Path(temp_dir) / "seen_posts.json"
            with patch.object(instagram, "RAPIDAPI_KEY", "real-key"), patch.object(
                instagram, "SEEN_POSTS_FILE", seen_file
            ), patch(
                "pipeline.scrapers.instagram.requests.get", side_effect=requests.RequestException("boom")
            ):
                posts = scrape_instagram(test_mode=False)

        self.assertEqual(posts, [])

    def test_rate_limit_429_skips_gracefully(self) -> None:
        """A 429 response on every endpoint must return [] without raising."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with TemporaryDirectory() as temp_dir:
            seen_file = Path(temp_dir) / "seen_posts.json"
            with patch.object(tiktok, "RAPIDAPI_KEY", "real-key"), patch.object(
                tiktok, "SEEN_POSTS_FILE", seen_file
            ), patch("pipeline.scrapers.tiktok.requests.get", return_value=mock_response):
                posts = scrape_tiktok(test_mode=False)

        self.assertEqual(posts, [])
        self.assertFalse(seen_file.exists(), "seen_posts.json should not be written when no endpoints succeed")

    def test_test_mode_returns_mock_posts_without_api_keys(self) -> None:
        with patch.object(tiktok, "RAPIDAPI_KEY", ""), patch.object(instagram, "RAPIDAPI_KEY", ""):
            tiktok_posts = scrape_tiktok(test_mode=True)
            instagram_posts = scrape_instagram(test_mode=True)
        self.assertIsInstance(tiktok_posts, list)
        self.assertIsInstance(instagram_posts, list)
        self.assertTrue(tiktok_posts)
        self.assertTrue(instagram_posts)


class SeenPostsTests(unittest.TestCase):
    """Verify dedup persistence edge cases."""

    def setUp(self) -> None:
        self.logger = logging.getLogger("test")

    def test_load_returns_empty_dict_when_file_does_not_exist(self) -> None:
        with TemporaryDirectory() as temp_dir:
            nonexistent = Path(temp_dir) / "subdir" / "seen_posts.json"
            result = load_seen_posts(nonexistent, self.logger)
        self.assertEqual(result, {})

    def test_load_returns_empty_dict_on_corrupt_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            corrupt = Path(temp_dir) / "seen_posts.json"
            corrupt.write_text("{{not valid json}}")
            result = load_seen_posts(corrupt, self.logger)
        self.assertEqual(result, {})

    def test_load_returns_empty_dict_when_file_contains_list(self) -> None:
        with TemporaryDirectory() as temp_dir:
            bad_type = Path(temp_dir) / "seen_posts.json"
            bad_type.write_text(json.dumps([1, 2, 3]))
            result = load_seen_posts(bad_type, self.logger)
        self.assertEqual(result, {})

    def test_save_creates_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            nested = Path(temp_dir) / "a" / "b" / "seen_posts.json"
            save_seen_posts(nested, {"tiktok_x": {"times_seen": 1}}, self.logger)
            self.assertTrue(nested.exists())
            reloaded = json.loads(nested.read_text())
            self.assertEqual(reloaded["tiktok_x"]["times_seen"], 1)

    def test_roundtrip_load_save_load_preserves_data(self) -> None:
        original = {
            "tiktok_abc": {"first_seen": "2026-03-31T10:00:00Z", "times_seen": 3},
            "instagram_xyz": {"first_seen": "2026-03-31T12:00:00Z", "times_seen": 1},
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "seen_posts.json"
            save_seen_posts(path, original, self.logger)
            reloaded = load_seen_posts(path, self.logger)
        self.assertEqual(reloaded, original)


class NormalizeTimestampTests(unittest.TestCase):
    """Verify timestamp normalization across all input formats."""

    def test_none_and_zero_return_none(self) -> None:
        self.assertIsNone(normalize_timestamp(None))
        self.assertIsNone(normalize_timestamp(0))
        self.assertIsNone(normalize_timestamp(""))
        self.assertIsNone(normalize_timestamp("   "))

    def test_unix_seconds_produces_z_iso(self) -> None:
        result = normalize_timestamp(1743379200)  # 2025-03-31T00:00:00Z
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("Z"))
        self.assertIn("2025-03-31", result)

    def test_unix_milliseconds_produces_same_result_as_seconds(self) -> None:
        seconds = normalize_timestamp(1743379200)
        millis = normalize_timestamp(1743379200000)
        self.assertEqual(seconds, millis)

    def test_iso_z_string_passes_through(self) -> None:
        result = normalize_timestamp("2026-03-30T23:15:00Z")
        self.assertEqual(result, "2026-03-30T23:15:00Z")

    def test_iso_with_timezone_offset_converts_to_utc(self) -> None:
        result = normalize_timestamp("2026-03-30T23:15:00+05:30")
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("Z"))
        self.assertIn("2026-03-30T17:45:00Z", result)

    def test_date_only_string_produces_midnight_utc(self) -> None:
        result = normalize_timestamp("2026-03-30")
        self.assertIsNotNone(result)
        self.assertIn("2026-03-30", result)
        self.assertTrue(result.endswith("Z"))

    def test_garbage_string_returns_none(self) -> None:
        self.assertIsNone(normalize_timestamp("not-a-date"))
        self.assertIsNone(normalize_timestamp("garbage"))

    def test_string_digit_unix_timestamp(self) -> None:
        result = normalize_timestamp("1743379200")
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("Z"))


class SafeIntTests(unittest.TestCase):
    """Verify safe_int edge cases including the OverflowError fix."""

    def test_infinity_returns_zero(self) -> None:
        self.assertEqual(safe_int(math.inf), 0)
        self.assertEqual(safe_int(-math.inf), 0)
        self.assertEqual(safe_int(float("inf")), 0)
        self.assertEqual(safe_int(float("-inf")), 0)

    def test_none_empty_false_return_zero(self) -> None:
        self.assertEqual(safe_int(None), 0)
        self.assertEqual(safe_int(""), 0)
        self.assertEqual(safe_int(False), 0)

    def test_string_float_truncates(self) -> None:
        self.assertEqual(safe_int("3.9"), 3)
        self.assertEqual(safe_int("3.0"), 3)

    def test_zero_returns_zero(self) -> None:
        self.assertEqual(safe_int(0), 0)
        self.assertEqual(safe_int("0"), 0)

    def test_negative_values(self) -> None:
        self.assertEqual(safe_int(-5), -5)
        self.assertEqual(safe_int("-5"), -5)

    def test_garbage_string_returns_zero(self) -> None:
        self.assertEqual(safe_int("not-a-number"), 0)


class ApiKeyPlaceholderTests(unittest.TestCase):
    """Verify _is_missing_api_key catches the same patterns config does."""

    # Lowercase placeholders come from config; uppercase variants exercise the
    # normalization inside _is_missing_api_key().
    _EXPECTED_BLOCKED = [
        *sorted(config._PLACEHOLDER_VALUES),
        "REPLACE_ME", "REPLACE-ME", "YOUR-KEY-HERE",
        "YOUR-TOKEN-HERE", "YOUR-CHANNEL-ID", "YOUR-BOT-TOKEN",
        "CHANGEME", "TODO", "NULL", "NONE",
    ]

    def test_scraper_placeholder_set_matches_config(self) -> None:
        self.assertEqual(tiktok._API_KEY_PLACEHOLDERS, config._PLACEHOLDER_VALUES)
        self.assertEqual(instagram._API_KEY_PLACEHOLDERS, config._PLACEHOLDER_VALUES)

    def test_tiktok_blocks_all_placeholder_patterns(self) -> None:
        for val in self._EXPECTED_BLOCKED:
            with self.subTest(value=val):
                self.assertTrue(
                    tiktok._is_missing_api_key(val),
                    msg=f"TikTok should block RAPIDAPI_KEY={val!r}",
                )

    def test_instagram_blocks_all_placeholder_patterns(self) -> None:
        for val in self._EXPECTED_BLOCKED:
            with self.subTest(value=val):
                self.assertTrue(
                    instagram._is_missing_api_key(val),
                    msg=f"Instagram should block RAPIDAPI_KEY={val!r}",
                )

    def test_real_key_is_not_blocked(self) -> None:
        self.assertFalse(tiktok._is_missing_api_key("sk-real-rapidapi-key-abc123"))
        self.assertFalse(instagram._is_missing_api_key("sk-real-rapidapi-key-abc123"))


class ExtractItemsTests(unittest.TestCase):
    """Verify extract_items handles variable API payload shapes."""

    def test_raw_list_of_dicts(self) -> None:
        result = extract_items([{"id": 1}, {"id": 2}])
        self.assertEqual(result, [{"id": 1}, {"id": 2}])

    def test_dict_with_data_key(self) -> None:
        result = extract_items({"data": [{"id": 1}]})
        self.assertEqual(result, [{"id": 1}])

    def test_dict_with_aweme_list_key(self) -> None:
        result = extract_items({"aweme_list": [{"aweme_id": "x"}]})
        self.assertEqual(result, [{"aweme_id": "x"}])

    def test_nested_dict_unwraps(self) -> None:
        result = extract_items({"response": {"data": [{"id": 1}]}})
        self.assertEqual(result, [{"id": 1}])

    def test_empty_preferred_list_falls_through_to_later_key(self) -> None:
        result = extract_items({"data": [], "items": [{"id": 1}]})
        self.assertEqual(result, [{"id": 1}])

    def test_string_payload_returns_empty(self) -> None:
        self.assertEqual(extract_items("just a string"), [])

    def test_none_payload_returns_empty(self) -> None:
        self.assertEqual(extract_items(None), [])

    def test_empty_dict_returns_empty(self) -> None:
        self.assertEqual(extract_items({}), [])

    def test_data_key_is_string_not_list(self) -> None:
        self.assertEqual(extract_items({"data": "not-a-list"}), [])

    def test_mixed_list_excludes_non_dicts(self) -> None:
        result = extract_items([{"id": 1}, "string", 42])
        self.assertEqual(result, [{"id": 1}])


class NormalizePostTests(unittest.TestCase):
    """Verify _normalize_post handles real-world API shapes and edge cases."""

    def test_normalize_post_returns_none_for_missing_post_id(self) -> None:
        cases = [
            (tiktok._normalize_post, {"desc": "some caption", "stats": {"play_count": 1000}}),
            (instagram._normalize_post, {"caption_text": "some caption", "like_count": 100}),
        ]
        for normalize_fn, raw in cases:
            with self.subTest(platform=normalize_fn.__module__.split(".")[-1]):
                self.assertIsNone(normalize_fn(raw, "2026-03-31T10:00:00Z"))

    def test_tiktok_nested_stats_shape(self) -> None:
        """Real Scraptik TikTok response shape with nested stats/author."""
        raw = {
            "aweme_id": "7123456789",
            "desc": "Tutorial with #nailtok",
            "author": {
                "unique_id": "nailcreator",
                "follower_count": 12000,
            },
            "stats": {
                "play_count": 95000,
                "digg_count": 8400,
                "comment_count": 210,
                "share_count": 1100,
                "collect_count": 1500,
            },
            "music": {
                "title": "trending sound",
                "authorName": "soundcreator",
            },
            "create_time": 1743379200,
        }
        post = tiktok._normalize_post(raw, "2026-03-31T10:00:00Z")
        self.assertIsNotNone(post)
        self.assertEqual(post["post_id"], "7123456789")
        self.assertEqual(post["author"], "nailcreator")
        self.assertEqual(post["author_followers"], 12000)
        self.assertEqual(post["views"], 95000)
        self.assertEqual(post["likes"], 8400)
        self.assertEqual(post["shares"], 1100)
        self.assertEqual(post["saves"], 1500)
        self.assertEqual(post["audio_name"], "trending sound")
        self.assertEqual(post["audio_author"], "soundcreator")
        self.assertIsNotNone(post["posted_at"])
        self.assertTrue(post["posted_at"].endswith("Z"))
        self.assertEqual(tuple(post.keys()), STANDARD_POST_KEYS)

    def test_instagram_nested_user_shape(self) -> None:
        """Real Scraptik Instagram Reel response shape."""
        raw = {
            "id": "ig_987654",
            "user": {
                "username": "reelcreator",
                "follower_count": 8500,
            },
            "caption": {"text": "Great reel #calpoly #tutorial"},
            "play_count": 55000,
            "like_count": 6200,
            "comment_count": 88,
            "save_count": 1100,
            "clips_music_attribution_info": {
                "song_name": "ambient track",
                "artist_name": "trackmaker",
            },
            "taken_at": 1743379200,
        }
        post = instagram._normalize_post(raw, "2026-03-31T10:00:00Z")
        self.assertIsNotNone(post)
        self.assertEqual(post["post_id"], "ig_987654")
        self.assertEqual(post["author"], "reelcreator")
        self.assertEqual(post["author_followers"], 8500)
        self.assertEqual(post["views"], 55000)
        self.assertEqual(post["likes"], 6200)
        self.assertEqual(post["saves"], 1100)
        self.assertEqual(post["audio_name"], "ambient track")
        self.assertEqual(post["audio_author"], "trackmaker")
        self.assertIsNotNone(post["posted_at"])
        self.assertTrue(post["posted_at"].endswith("Z"))
        self.assertEqual(tuple(post.keys()), STANDARD_POST_KEYS)

    def test_tiktok_all_missing_fields_produce_safe_defaults(self) -> None:
        """A post with only a valid ID must not crash and must use safe defaults."""
        raw = {"aweme_id": "minimal_post"}
        post = tiktok._normalize_post(raw, "2026-03-31T10:00:00Z")
        self.assertIsNotNone(post)
        self.assertEqual(post["author"], "")
        self.assertEqual(post["views"], 0)
        self.assertEqual(post["likes"], 0)
        self.assertEqual(post["shares"], 0)
        self.assertEqual(post["saves"], 0)
        self.assertIsNone(post["audio_name"])
        self.assertIsNone(post["posted_at"])
        self.assertIsInstance(post["hashtags"], list)

    def test_tiktok_url_constructed_from_author_and_id_when_missing(self) -> None:
        raw = {
            "aweme_id": "7999",
            "author": {"unique_id": "mycreator"},
        }
        post = tiktok._normalize_post(raw, "2026-03-31T10:00:00Z")
        self.assertIsNotNone(post)
        self.assertIn("mycreator", post["url"])
        self.assertIn("7999", post["url"])


if __name__ == "__main__":
    unittest.main()
