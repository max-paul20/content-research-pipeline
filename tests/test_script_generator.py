"""Unit tests for the Sonnet-powered script generator."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from pipeline.analyzer_legacy import _mock_analyze
from pipeline.script_generator import (
    _build_user_prompt,
    _extract_brief,
    _split_by_campus,
    generate_scripts,
)


def _make_analyzed_post(post_id, campus="both", score=80, trend_type="audio_driven"):
    """Build a minimal analyzed post dict."""

    return {
        "post_id": post_id,
        "platform": "tiktok",
        "author": "testuser",
        "author_followers": 5000,
        "caption": f"test caption for {post_id}",
        "hashtags": ["beauty", "grwm"],
        "views": 50000,
        "likes": 5000,
        "comments": 200,
        "shares": 100,
        "saves": 300,
        "url": f"https://tiktok.com/@testuser/video/{post_id}",
        "audio_name": "trending sound",
        "audio_author": "artist",
        "posted_at": "2026-03-30T12:00:00Z",
        "scraped_at": "2026-03-31T00:00:00Z",
        "raw_data": {},
        "virality_score": 85,
        "engagement_velocity": "high",
        "trend_type": trend_type,
        "virality_reason": "test reason",
        "audio_lifecycle": "rising",
        "relevance_score": 90,
        "recommended_campus": campus,
        "composite_score": score,
    }


def _make_raw_post(post_id, views=50000, likes=5000):
    """Build a minimal raw post dict for analyzer-to-generator contract tests."""

    return {
        "post_id": post_id,
        "platform": "tiktok",
        "author": "testuser",
        "author_followers": 5000,
        "caption": f"raw post caption for {post_id}",
        "hashtags": ["beauty", "grwm"],
        "views": views,
        "likes": likes,
        "comments": 200,
        "shares": 100,
        "saves": 300,
        "url": f"https://tiktok.com/@testuser/video/{post_id}",
        "audio_name": "trending sound",
        "audio_author": "artist",
        "posted_at": "2026-03-30T12:00:00Z",
        "scraped_at": "2026-03-31T00:00:00Z",
        "raw_data": {},
    }


def _anthropic_response(text):
    """Build a mock Anthropic API response body."""

    return json.dumps(
        {
            "content": [{"type": "text", "text": text}],
            "model": "claude-sonnet-4-20250514",
            "role": "assistant",
        }
    )


class TestModeTests(unittest.TestCase):
    """Verify test_mode returns mock briefs."""

    def test_test_mode_returns_scripts(self) -> None:
        posts = [
            _make_analyzed_post("p1", campus="uofa", score=90),
            _make_analyzed_post("p2", campus="calpoly", score=85),
            _make_analyzed_post("p3", campus="both", score=80),
        ]
        result = generate_scripts(posts, test_mode=True)

        self.assertGreater(len(result), 0)
        for script in result:
            self.assertIn("campus", script)
            self.assertIn("brief", script)
            self.assertIn("source_url", script)
            self.assertIn("generated_at", script)
            self.assertIn("trend_type", script)

    def test_test_mode_respects_scripts_per_campus(self) -> None:
        posts = [
            _make_analyzed_post(f"uofa_{i}", campus="uofa", score=90 - i)
            for i in range(5)
        ] + [
            _make_analyzed_post(f"calpoly_{i}", campus="calpoly", score=90 - i)
            for i in range(5)
        ]
        result = generate_scripts(posts, test_mode=True)

        az_count = sum(1 for s in result if s["campus"] == "uofa")
        cp_count = sum(1 for s in result if s["campus"] == "calpoly")
        self.assertEqual(az_count, 3)  # SCRIPTS_PER_CAMPUS default
        self.assertEqual(cp_count, 3)

    def test_test_mode_briefs_reference_campus(self) -> None:
        posts = [
            _make_analyzed_post("p1", campus="uofa"),
            _make_analyzed_post("p2", campus="calpoly"),
        ]
        result = generate_scripts(posts, test_mode=True)

        az_scripts = [s for s in result if s["campus"] == "uofa"]
        cp_scripts = [s for s in result if s["campus"] == "calpoly"]

        if az_scripts:
            self.assertIn("Unigliss", az_scripts[0]["brief"])
        if cp_scripts:
            self.assertIn("Unigliss", cp_scripts[0]["brief"])

    def test_target_campus_only_generates_requested_bucket(self) -> None:
        posts = [
            _make_analyzed_post("p1", campus="both", score=90),
            _make_analyzed_post("p2", campus="calpoly", score=80),
        ]

        result = generate_scripts(posts, test_mode=True, target_campus="uofa")

        self.assertTrue(result)
        self.assertTrue(all(script["campus"] == "uofa" for script in result))
        self.assertTrue(all("#cal poly" not in script["brief"].lower() for script in result))


class CampusSplitTests(unittest.TestCase):
    """Verify campus splitting logic."""

    def test_split_uofa_only(self) -> None:
        posts = [_make_analyzed_post("p1", campus="uofa")]
        az, cp = _split_by_campus(posts)
        self.assertEqual(len(az), 1)
        self.assertEqual(len(cp), 0)

    def test_split_calpoly_only(self) -> None:
        posts = [_make_analyzed_post("p1", campus="calpoly")]
        az, cp = _split_by_campus(posts)
        self.assertEqual(len(az), 0)
        self.assertEqual(len(cp), 1)

    def test_split_both_goes_to_both_buckets(self) -> None:
        posts = [_make_analyzed_post("p1", campus="both")]
        az, cp = _split_by_campus(posts)
        self.assertEqual(len(az), 1)
        self.assertEqual(len(cp), 1)

    def test_split_sorts_by_composite_score(self) -> None:
        posts = [
            _make_analyzed_post("p1", campus="uofa", score=60),
            _make_analyzed_post("p2", campus="uofa", score=90),
            _make_analyzed_post("p3", campus="uofa", score=75),
        ]
        az, _ = _split_by_campus(posts)
        scores = [p["composite_score"] for p in az]
        self.assertEqual(scores, [90, 75, 60])


class UserPromptTests(unittest.TestCase):
    """Verify user prompt formatting."""

    def test_user_prompt_includes_post_data(self) -> None:
        post = _make_analyzed_post("p1")
        prompt = _build_user_prompt(post)

        self.assertIn("test caption for p1", prompt)
        self.assertIn("50,000", prompt)  # views formatted
        self.assertIn("trending sound", prompt)
        self.assertIn("Virality Score: 85", prompt)
        self.assertIn("audio_driven", prompt)


class ContractTests(unittest.TestCase):
    """Verify schema compatibility between pipeline stages."""

    def test_analyzer_output_feeds_script_generator(self) -> None:
        with patch("pipeline.analyzer_legacy.config") as mock_config:
            mock_config.ANALYZER_MIN_SCORE = 0
            mock_config.ANALYZER_TOP_N = 15
            analyzed = _mock_analyze(
                [
                    _make_raw_post("raw_1", views=80000, likes=9000),
                    _make_raw_post("raw_2", views=72000, likes=8500),
                ]
            )

        scripts = generate_scripts(analyzed, test_mode=True)

        self.assertTrue(scripts)
        for script in scripts:
            self.assertIn("campus", script)
            self.assertIn("brief", script)
            self.assertIn("source_url", script)
            self.assertIn("generated_at", script)


class ExtractBriefTests(unittest.TestCase):
    """Verify Anthropic response parsing."""

    def test_valid_response(self) -> None:
        raw = _anthropic_response("This is the brief text")
        result = _extract_brief(raw)
        self.assertEqual(result, "This is the brief text")

    def test_malformed_response(self) -> None:
        result = _extract_brief("not json")
        self.assertEqual(result, "")

    def test_empty_content_blocks(self) -> None:
        raw = json.dumps({"content": []})
        result = _extract_brief(raw)
        self.assertEqual(result, "")


class ApiIntegrationTests(unittest.TestCase):
    """Verify Anthropic API call patterns."""

    @patch("pipeline.script_generator.requests.post")
    def test_generates_correct_number_of_scripts(self, mock_post) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _anthropic_response("Mock brief")
        mock_post.return_value = mock_response

        posts = [
            _make_analyzed_post("p1", campus="uofa", score=90),
            _make_analyzed_post("p2", campus="uofa", score=85),
            _make_analyzed_post("p3", campus="calpoly", score=80),
        ]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-real"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            result = generate_scripts(posts)

        self.assertEqual(len(result), 3)
        self.assertEqual(mock_post.call_count, 3)

    @patch("pipeline.script_generator.requests.post")
    def test_api_headers_correct(self, mock_post) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _anthropic_response("Brief")
        mock_post.return_value = mock_response

        posts = [_make_analyzed_post("p1", campus="uofa")]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            generate_scripts(posts)

        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
        self.assertEqual(headers["x-api-key"], "sk-ant-test")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.script_generator.requests.post")
    def test_api_failure_skips_script(self, mock_post, mock_sleep) -> None:
        mock_post.side_effect = requests.ConnectionError("timeout")

        posts = [_make_analyzed_post("p1", campus="uofa")]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            result = generate_scripts(posts)

        self.assertEqual(result, [])
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.script_generator.requests.post")
    def test_non_200_status_skips_script(self, mock_post, mock_sleep) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service unavailable"
        mock_response.headers = {}
        mock_post.return_value = mock_response

        posts = [_make_analyzed_post("p1", campus="uofa")]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            result = generate_scripts(posts)

        self.assertEqual(result, [])
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.script_generator.requests.post")
    def test_5xx_retries_then_generates_script(self, mock_post, mock_sleep) -> None:
        retry_response = MagicMock()
        retry_response.status_code = 503
        retry_response.text = "Service unavailable"
        retry_response.headers = {}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = _anthropic_response("Mock brief")
        success_response.headers = {}
        mock_post.side_effect = [retry_response, success_response]

        posts = [_make_analyzed_post("p1", campus="uofa")]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            result = generate_scripts(posts)

        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)
        self.assertEqual(len(result), 1)

    @patch("pipeline.script_generator.requests.post")
    def test_401_logs_invalid_key_without_retry(self, mock_post) -> None:
        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "Unauthorized"
        unauthorized.headers = {}
        mock_post.return_value = unauthorized

        posts = [_make_analyzed_post("p1", campus="uofa")]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            with self.assertLogs("pipeline.script_generator", level="ERROR") as captured:
                result = generate_scripts(posts)

        self.assertEqual(result, [])
        self.assertEqual(mock_post.call_count, 1)
        self.assertTrue(any("API key invalid or expired for Anthropic." in line for line in captured.output))

    @patch("pipeline.script_generator.requests.post")
    def test_target_campus_prevents_off_target_calls(self, mock_post) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _anthropic_response("Mock brief")
        mock_post.return_value = mock_response

        posts = [_make_analyzed_post("p1", campus="both", score=90)]

        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = False
            mock_config.ANTHROPIC_API_KEY = "sk-ant-test"
            mock_config.ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
            mock_config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_config.SCRIPTS_PER_CAMPUS = 3

            result = generate_scripts(posts, target_campus="uofa")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["campus"], "uofa")
        self.assertEqual(mock_post.call_count, 1)

    def test_placeholder_key_skips(self) -> None:
        posts = [_make_analyzed_post("p1")]
        with patch("pipeline.script_generator.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config._is_placeholder.return_value = True
            mock_config.ANTHROPIC_API_KEY = "your-anthropic-key"

            result = generate_scripts(posts)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
