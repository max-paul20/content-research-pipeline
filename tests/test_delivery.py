"""Unit tests for the Telegram delivery module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from pipeline.delivery import (
    _format_message,
    deliver_scripts,
)


def _make_script(campus="uofa", trend_type="audio_driven"):
    """Build a minimal script dict for testing."""

    return {
        "campus": campus,
        "trend_type": trend_type,
        "brief": "HOOK: POV beauty hack\nKEY BEATS: show product\nDIALOGUE: so good",
        "source_url": "https://tiktok.com/@test/video/123",
        "generated_at": "2026-03-31T12:00:00Z",
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
