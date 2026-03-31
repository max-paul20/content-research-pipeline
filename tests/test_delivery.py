"""Unit tests for the Telegram delivery module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from pipeline.script_generator import generate_scripts
from pipeline.delivery import (
    _format_message,
    deliver_scripts,
)


def _make_script(campus="uofa", trend_type="audio_driven"):
    """Build a minimal script dict for testing."""

    return {
        "campus": campus,
        "trend_type": trend_type,
        "brief": (
            "\U0001f3ac HOOK: POV beauty hack\n"
            "\U0001f4dd KEY BEATS:\n"
            "- show product\n"
            "\U0001f5e3\ufe0f SUGGESTED DIALOGUE:\n"
            "\"so good\"\n"
            "\U0001f3b5 AUDIO: trending sound\n"
            "#\ufe0f\u20e3 HASHTAGS: #beauty #uofa #unigliss #grwm #campusglam\n"
            "\U0001f4cd CAMPUS TIE-IN: Old Main"
        ),
        "source_url": "https://tiktok.com/@test/video/123",
        "generated_at": "2026-03-31T12:00:00Z",
    }


def _make_analyzed_post(post_id="p1", campus="uofa"):
    """Build a minimal analyzed post for generator-to-delivery contract tests."""

    return {
        "post_id": post_id,
        "platform": "tiktok",
        "author": "testuser",
        "author_followers": 5000,
        "caption": f"caption for {post_id}",
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
        "trend_type": "audio_driven",
        "virality_reason": "test reason",
        "audio_lifecycle": "rising",
        "relevance_score": 90,
        "recommended_campus": campus,
        "composite_score": 76.5,
    }


class FormatTests(unittest.TestCase):
    """Verify Telegram message formatting."""

    def test_arizona_format_has_cactus_emoji(self) -> None:
        msg = _format_message(_make_script(campus="uofa"))
        self.assertIn("\U0001f335", msg)
        self.assertIn("Arizona", msg)

    def test_calpoly_format_has_horse_emoji(self) -> None:
        msg = _format_message(_make_script(campus="calpoly"))
        self.assertIn("\U0001f40e", msg)
        self.assertIn("Cal Poly", msg)

    def test_format_includes_trend_type(self) -> None:
        msg = _format_message(_make_script(trend_type="campus_specific"))
        self.assertIn("Campus Specific", msg)

    def test_format_includes_brief_body(self) -> None:
        msg = _format_message(_make_script())
        self.assertIn("HOOK: POV beauty hack", msg)

    def test_format_includes_source_url(self) -> None:
        msg = _format_message(_make_script())
        self.assertIn("Source: https://tiktok.com/@test/video/123", msg)

    def test_format_includes_timestamp(self) -> None:
        msg = _format_message(_make_script())
        self.assertIn("Generated: 2026-03-31T12:00:00Z", msg)


class DeliveryOrderTests(unittest.TestCase):
    """Verify Arizona-first ordering and separator."""

    def test_empty_scripts_returns_zeros(self) -> None:
        result = deliver_scripts([], test_mode=True)
        self.assertEqual(result, {"sent": 0, "failed": 0})

    def test_dry_run_counts_scripts(self) -> None:
        scripts = [
            _make_script(campus="uofa"),
            _make_script(campus="uofa"),
            _make_script(campus="calpoly"),
        ]
        result = deliver_scripts(scripts, test_mode=True)
        self.assertEqual(result["sent"], 3)
        self.assertEqual(result["failed"], 0)

    @patch("pipeline.delivery._send_or_log")
    def test_arizona_sent_before_calpoly(self, mock_send) -> None:
        mock_send.return_value = True

        scripts = [
            _make_script(campus="calpoly"),
            _make_script(campus="uofa"),
        ]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = True
            mock_config.DRY_RUN = False
            deliver_scripts(scripts)

        calls = mock_send.call_args_list
        # First call should be Arizona, then separator, then Cal Poly
        first_msg = calls[0][0][0]
        self.assertIn("Arizona", first_msg)

    @patch("pipeline.delivery._send_or_log")
    def test_separator_between_campuses(self, mock_send) -> None:
        mock_send.return_value = True

        scripts = [
            _make_script(campus="uofa"),
            _make_script(campus="calpoly"),
        ]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = True
            mock_config.DRY_RUN = False
            deliver_scripts(scripts)

        call_texts = [c[0][0] for c in mock_send.call_args_list]
        self.assertIn("---", call_texts)


class ContractTests(unittest.TestCase):
    """Verify script generator output works with delivery formatting."""

    def test_script_generator_output_formats_for_delivery(self) -> None:
        scripts = generate_scripts(
            [_make_analyzed_post(post_id="generated_1", campus="uofa")],
            test_mode=True,
            target_campus="uofa",
        )

        self.assertTrue(scripts)
        message = _format_message(scripts[0])
        result = deliver_scripts(scripts, test_mode=True)

        self.assertIn("Arizona", message)
        self.assertIn("SUGGESTED DIALOGUE", message)
        self.assertIn("Source: https://tiktok.com/@testuser/video/generated_1", message)
        self.assertEqual(result, {"sent": 1, "failed": 0})


class DryRunTests(unittest.TestCase):
    """Verify dry run and test mode skip real sends."""

    def test_test_mode_skips_real_sends(self) -> None:
        scripts = [_make_script()]
        with patch("pipeline.delivery.requests.post") as mock_post:
            result = deliver_scripts(scripts, test_mode=True)

        mock_post.assert_not_called()
        self.assertEqual(result["sent"], 1)

    @patch("pipeline.delivery.config")
    def test_dry_run_flag_skips_real_sends(self, mock_config) -> None:
        mock_config.is_test_mode.return_value = False
        mock_config.DRY_RUN = True
        mock_config._is_placeholder.return_value = False
        mock_config.TELEGRAM_BOT_TOKEN = "real-token"

        scripts = [_make_script()]
        with patch("pipeline.delivery.requests.post") as mock_post:
            result = deliver_scripts(scripts)

        mock_post.assert_not_called()
        self.assertEqual(result["sent"], 1)


class ApiFailureTests(unittest.TestCase):
    """Verify Telegram API error handling."""

    @patch("pipeline.delivery.requests.post")
    def test_send_failure_increments_failed(self, mock_post) -> None:
        mock_post.side_effect = requests.ConnectionError("timeout")

        scripts = [_make_script()]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            result = deliver_scripts(scripts)

        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["failed"], 1)

    @patch("pipeline.delivery.requests.post")
    def test_non_200_increments_failed(self, mock_post) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_post.return_value = mock_response

        scripts = [_make_script()]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            result = deliver_scripts(scripts)

        self.assertEqual(result["failed"], 1)

    def test_placeholder_token_skips(self) -> None:
        scripts = [_make_script()]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = True
            mock_config.TELEGRAM_BOT_TOKEN = "your-bot-token"

            result = deliver_scripts(scripts)

        self.assertEqual(result, {"sent": 0, "failed": 0})


if __name__ == "__main__":
    unittest.main()
