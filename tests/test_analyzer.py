"""Unit tests for the Gemini-powered trend analyzer."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from pipeline.analyzer_legacy import (
    _extract_json_array,
    _format_batch,
    _merge_analyses,
    _mock_analyze,
    _rank_and_filter,
    analyze_posts,
)


def _make_post(post_id, views=1000, likes=100, platform="tiktok"):
    """Build a minimal post dict for testing."""

    return {
        "post_id": post_id,
        "platform": platform,
        "author": "testuser",
        "author_followers": 5000,
        "caption": "test caption #beauty",
        "hashtags": ["beauty"],
        "views": views,
        "likes": likes,
        "comments": 10,
        "shares": 5,
        "saves": 8,
        "url": f"https://tiktok.com/@testuser/video/{post_id}",
        "audio_name": "trending sound",
        "audio_author": "artist",
        "posted_at": "2026-03-30T12:00:00Z",
        "scraped_at": "2026-03-31T00:00:00Z",
        "raw_data": {},
    }


def _gemini_api_response(analyses):
    """Wrap analysis results in Gemini API response structure."""

    return json.dumps(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(analyses)}],
                    }
                }
            ]
        }
    )


class TestModeTests(unittest.TestCase):
    """Verify test_mode returns deterministic mock scores."""

    def test_test_mode_returns_enriched_posts(self) -> None:
        posts = [_make_post("tk_001"), _make_post("tk_002"), _make_post("tk_003")]
        result = analyze_posts(posts, test_mode=True)

        self.assertGreater(len(result), 0)
        for post in result:
            self.assertIn("virality_score", post)
            self.assertIn("composite_score", post)
            self.assertIn("recommended_campus", post)
            self.assertIn("trend_type", post)
            self.assertIn("engagement_velocity", post)
            self.assertIn("audio_lifecycle", post)
            self.assertIn("virality_reason", post)
            self.assertIn("relevance_score", post)
            # Original fields preserved
            self.assertIn("post_id", post)
            self.assertIn("caption", post)

    def test_test_mode_is_deterministic(self) -> None:
        posts = [_make_post("tk_001"), _make_post("tk_002")]
        result1 = analyze_posts(posts, test_mode=True)
        result2 = analyze_posts(posts, test_mode=True)

        self.assertEqual(len(result1), len(result2))
        for r1, r2 in zip(result1, result2):
            self.assertEqual(r1["virality_score"], r2["virality_score"])
            self.assertEqual(r1["composite_score"], r2["composite_score"])

    def test_test_mode_scores_in_valid_range(self) -> None:
        posts = [_make_post(f"post_{i}") for i in range(20)]
        result = analyze_posts(posts, test_mode=True)

        for post in result:
            self.assertGreaterEqual(post["virality_score"], 0)
            self.assertLessEqual(post["virality_score"], 100)
            self.assertGreaterEqual(post["relevance_score"], 0)
            self.assertLessEqual(post["relevance_score"], 100)
            self.assertGreaterEqual(post["composite_score"], 0)

    def test_test_mode_filters_below_min_score(self) -> None:
        posts = [_make_post(f"post_{i}") for i in range(50)]
        result = analyze_posts(posts, test_mode=True)

        for post in result:
            self.assertGreaterEqual(post["composite_score"], 50)  # ANALYZER_MIN_SCORE default

    def test_test_mode_caps_at_top_n(self) -> None:
        posts = [_make_post(f"post_{i}") for i in range(50)]
        result = analyze_posts(posts, test_mode=True)

        self.assertLessEqual(len(result), 15)  # ANALYZER_TOP_N default

    def test_test_mode_sorted_by_composite_score_descending(self) -> None:
        posts = [_make_post(f"post_{i}") for i in range(20)]
        result = analyze_posts(posts, test_mode=True)

        scores = [p["composite_score"] for p in result]
        self.assertEqual(scores, sorted(scores, reverse=True))


class BatchingTests(unittest.TestCase):
    """Verify batch formation and API call patterns."""

    def test_format_batch_includes_key_fields(self) -> None:
        posts = [_make_post("tk_001")]
        batch_str = _format_batch(posts)
        batch_data = json.loads(batch_str)

        self.assertEqual(len(batch_data), 1)
        self.assertEqual(batch_data[0]["post_id"], "tk_001")
        self.assertIn("views", batch_data[0])
        self.assertIn("caption", batch_data[0])
        self.assertIn("audio_name", batch_data[0])

    @patch("pipeline.analyzer_legacy.requests.post")
    def test_batching_groups_posts_correctly(self, mock_post) -> None:
        """7 posts should produce 2 API calls (batch size 5)."""

        analysis = [
            {
                "post_id": f"post_{i}",
                "virality_score": 80,
                "engagement_velocity": "high",
                "trend_type": "audio_driven",
                "virality_reason": "test",
                "audio_lifecycle": "rising",
                "relevance_score": 80,
                "recommended_campus": "both",
            }
            for i in range(7)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        # First call returns analyses for posts 0-4, second for 5-6
        mock_response.text = _gemini_api_response(analysis[:5])
        mock_post.return_value = mock_response

        posts = [_make_post(f"post_{i}") for i in range(7)]

        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.GEMINI_API_KEY = "real-key"
            mock_config.GEMINI_API_ENDPOINT = "https://api.example.com/gemini"
            mock_config.GEMINI_ANALYSIS_TEMPERATURE = 0.3
            mock_config.MAX_GEMINI_CALLS_PER_RUN = 500
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15

            analyze_posts(posts)

        self.assertEqual(mock_post.call_count, 2)

    @patch("pipeline.analyzer_legacy.requests.post")
    def test_budget_stops_at_max_calls(self, mock_post) -> None:
        """API budget must stop making calls once limit is reached."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _gemini_api_response([])
        mock_post.return_value = mock_response

        posts = [_make_post(f"post_{i}") for i in range(25)]

        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.GEMINI_API_KEY = "real-key"
            mock_config.GEMINI_API_ENDPOINT = "https://api.example.com/gemini"
            mock_config.GEMINI_ANALYSIS_TEMPERATURE = 0.3
            mock_config.MAX_GEMINI_CALLS_PER_RUN = 2  # Only allow 2 calls
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15

            analyze_posts(posts)

        self.assertEqual(mock_post.call_count, 2)


class ScoringTests(unittest.TestCase):
    """Verify composite score computation and ranking."""

    def test_composite_score_calculation(self) -> None:
        enriched = [
            {"virality_score": 80, "relevance_score": 90, "composite_score": 0},
        ]
        _merge_analyses(
            [{"post_id": "p1"}],
            [{"post_id": "p1", "virality_score": 80, "relevance_score": 90}],
            result := [],
        )
        self.assertAlmostEqual(result[0]["composite_score"], 72.0)

    def test_rank_and_filter_removes_low_scores(self) -> None:
        posts = [
            {"post_id": "a", "composite_score": 80},
            {"post_id": "b", "composite_score": 30},
            {"post_id": "c", "composite_score": 60},
        ]
        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.ANALYZER_MIN_SCORE = 50
            mock_config.ANALYZER_TOP_N = 10
            result = _rank_and_filter(posts)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["post_id"], "a")
        self.assertEqual(result[1]["post_id"], "c")

    def test_rank_and_filter_caps_at_top_n(self) -> None:
        posts = [{"post_id": f"p{i}", "composite_score": 90 - i} for i in range(10)]
        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 3
            result = _rank_and_filter(posts)

        self.assertEqual(len(result), 3)


class JsonParsingTests(unittest.TestCase):
    """Verify Gemini response JSON extraction edge cases."""

    def test_clean_json_array(self) -> None:
        text = '[{"post_id": "a", "virality_score": 80}]'
        result = _extract_json_array(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["post_id"], "a")

    def test_json_in_code_fences(self) -> None:
        text = '```json\n[{"post_id": "a", "virality_score": 80}]\n```'
        result = _extract_json_array(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["post_id"], "a")

    def test_json_in_plain_fences(self) -> None:
        text = '```\n[{"post_id": "a"}]\n```'
        result = _extract_json_array(text)
        self.assertEqual(len(result), 1)

    def test_json_with_preamble_text(self) -> None:
        text = 'Here are the results:\n{"post_id": "a", "virality_score": 80, "relevance_score": 70}'
        result = _extract_json_array(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["post_id"], "a")
        self.assertEqual(result[0]["virality_score"], 80)

    def test_single_object_wrapped_in_list(self) -> None:
        text = '{"post_id": "a", "virality_score": 80}'
        result = _extract_json_array(text)
        self.assertEqual(len(result), 1)

    def test_malformed_json_returns_empty(self) -> None:
        text = "this is not json at all"
        with self.assertLogs("pipeline.analyzer_legacy", level="WARNING") as captured:
            result = _extract_json_array(text)
        self.assertEqual(result, [])
        self.assertTrue(any("Failed to parse Gemini JSON response" in line for line in captured.output))

    def test_truncated_json_returns_empty_and_logs_warning(self) -> None:
        text = '{"post_id": "a", "virality_score": 80'
        with self.assertLogs("pipeline.analyzer_legacy", level="WARNING") as captured:
            result = _extract_json_array(text)
        self.assertEqual(result, [])
        self.assertTrue(any("Failed to parse Gemini JSON response" in line for line in captured.output))

    def test_non_dict_items_filtered(self) -> None:
        text = '[{"post_id": "a"}, "garbage", 42]'
        result = _extract_json_array(text)
        self.assertEqual(len(result), 1)

    def test_wrong_schema_defaults_missing_and_invalid_fields(self) -> None:
        text = (
            '[{"post_id": "a", "virality_score": "high", "relevance_score": null, '
            '"trend_type": 42, "extra_field": "ignored"}]'
        )
        with self.assertLogs("pipeline.analyzer_legacy", level="WARNING") as captured:
            result = _extract_json_array(text)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["virality_score"], 0)
        self.assertEqual(result[0]["relevance_score"], 0)
        self.assertEqual(result[0]["trend_type"], "format_driven")
        self.assertTrue(any("missing or invalid virality_score" in line for line in captured.output))


class ApiFailureTests(unittest.TestCase):
    """Verify graceful handling of API errors."""

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.analyzer_legacy.requests.post")
    def test_request_exception_returns_empty(self, mock_post, mock_sleep) -> None:
        mock_post.side_effect = requests.ConnectionError("connection failed")

        posts = [_make_post("tk_001")]
        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.GEMINI_API_KEY = "real-key"
            mock_config.GEMINI_API_ENDPOINT = "https://api.example.com/gemini"
            mock_config.GEMINI_ANALYSIS_TEMPERATURE = 0.3
            mock_config.MAX_GEMINI_CALLS_PER_RUN = 500
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15

            result = analyze_posts(posts)

        self.assertEqual(result, [])
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.analyzer_legacy.requests.post")
    def test_non_200_status_returns_empty(self, mock_post, mock_sleep) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.headers = {}
        mock_post.return_value = mock_response

        posts = [_make_post("tk_001")]
        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.GEMINI_API_KEY = "real-key"
            mock_config.GEMINI_API_ENDPOINT = "https://api.example.com/gemini"
            mock_config.GEMINI_ANALYSIS_TEMPERATURE = 0.3
            mock_config.MAX_GEMINI_CALLS_PER_RUN = 500
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15

            result = analyze_posts(posts)

        self.assertEqual(result, [])
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.analyzer_legacy.requests.post")
    def test_5xx_retries_then_succeeds(self, mock_post, mock_sleep) -> None:
        retry_response = MagicMock()
        retry_response.status_code = 503
        retry_response.text = "Service unavailable"
        retry_response.headers = {}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = _gemini_api_response(
            [
                {
                    "post_id": "tk_001",
                    "virality_score": 80,
                    "engagement_velocity": "high",
                    "trend_type": "audio_driven",
                    "virality_reason": "test",
                    "audio_lifecycle": "rising",
                    "relevance_score": 85,
                    "recommended_campus": "both",
                }
            ]
        )
        mock_post.side_effect = [retry_response, success_response]

        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.GEMINI_API_KEY = "real-key"
            mock_config.GEMINI_API_ENDPOINT = "https://api.example.com/gemini"
            mock_config.GEMINI_ANALYSIS_TEMPERATURE = 0.3
            mock_config.MAX_GEMINI_CALLS_PER_RUN = 500
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15

            result = analyze_posts([_make_post("tk_001")])

        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)
        self.assertEqual(len(result), 1)

    @patch("pipeline.analyzer_legacy.requests.post")
    def test_401_logs_invalid_key_without_retry(self, mock_post) -> None:
        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "Unauthorized"
        unauthorized.headers = {}
        mock_post.return_value = unauthorized

        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.GEMINI_API_KEY = "real-key"
            mock_config.GEMINI_API_ENDPOINT = "https://api.example.com/gemini"
            mock_config.GEMINI_ANALYSIS_TEMPERATURE = 0.3
            mock_config.MAX_GEMINI_CALLS_PER_RUN = 500
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15

            with self.assertLogs("pipeline.analyzer_legacy", level="ERROR") as captured:
                result = analyze_posts([_make_post("tk_001")])

        self.assertEqual(result, [])
        self.assertEqual(mock_post.call_count, 1)
        self.assertTrue(any("API key invalid or expired for Gemini." in line for line in captured.output))

    def test_placeholder_api_key_skips_analysis(self) -> None:
        posts = [_make_post("tk_001")]
        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = True
            mock_config.GEMINI_API_KEY = "your-key-here"

            result = analyze_posts(posts)

        self.assertEqual(result, [])


class MergeTests(unittest.TestCase):
    """Verify analysis-to-post merge logic."""

    def test_missing_analysis_uses_defaults(self) -> None:
        batch = [{"post_id": "p1", "caption": "test"}]
        result: list = []
        _merge_analyses(batch, [], result)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["virality_score"], 0)
        self.assertEqual(result[0]["relevance_score"], 0)
        self.assertEqual(result[0]["composite_score"], 0.0)
        self.assertEqual(result[0]["engagement_velocity"], "low")
        self.assertEqual(result[0]["recommended_campus"], "both")

    def test_merge_preserves_original_fields(self) -> None:
        batch = [{"post_id": "p1", "caption": "original caption", "views": 5000}]
        analyses = [
            {"post_id": "p1", "virality_score": 85, "relevance_score": 90}
        ]
        result: list = []
        _merge_analyses(batch, analyses, result)

        self.assertEqual(result[0]["caption"], "original caption")
        self.assertEqual(result[0]["views"], 5000)
        self.assertEqual(result[0]["virality_score"], 85)


if __name__ == "__main__":
    unittest.main()
