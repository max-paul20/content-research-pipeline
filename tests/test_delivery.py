"""Unit tests for the Telegram delivery module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from pipeline.script_generator import generate_scripts
from pipeline.delivery import (
    _TELEGRAM_MESSAGE_LIMIT,
    _chunk_text,
    _format_message,
    deliver_report,
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

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.delivery.requests.post")
    def test_send_failure_increments_failed(self, mock_post, mock_sleep) -> None:
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
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [1, 2])

    @patch("pipeline.delivery.requests.post")
    def test_non_200_increments_failed(self, mock_post) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.headers = {}
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

    @patch("pipeline.http_utils.time.sleep")
    @patch("pipeline.delivery.requests.post")
    def test_rate_limit_retries_then_sends(self, mock_post, mock_sleep) -> None:
        retry_response = MagicMock()
        retry_response.status_code = 429
        retry_response.text = "Too Many Requests"
        retry_response.headers = {"Retry-After": "1"}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "ok"
        success_response.headers = {}
        mock_post.side_effect = [retry_response, success_response]

        scripts = [_make_script()]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            result = deliver_scripts(scripts)

        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)
        self.assertEqual(result, {"sent": 1, "failed": 0})

    @patch("pipeline.delivery.requests.post")
    def test_401_logs_invalid_key_without_retry(self, mock_post) -> None:
        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "Unauthorized"
        unauthorized.headers = {}
        mock_post.return_value = unauthorized

        scripts = [_make_script()]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            with self.assertLogs("pipeline.delivery", level="ERROR") as captured:
                result = deliver_scripts(scripts)

        self.assertEqual(result, {"sent": 0, "failed": 1})
        self.assertEqual(mock_post.call_count, 1)
        self.assertTrue(any("API key invalid or expired for Telegram." in line for line in captured.output))

    def test_placeholder_token_skips(self) -> None:
        scripts = [_make_script()]

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = True
            mock_config.TELEGRAM_BOT_TOKEN = "your-bot-token"

            result = deliver_scripts(scripts)

        self.assertEqual(result, {"sent": 0, "failed": 0})


class DeliverReportTests(unittest.TestCase):
    """Verify single-message report delivery semantics."""

    def test_empty_report_is_noop(self) -> None:
        self.assertEqual(deliver_report(""), {"sent": 0, "failed": 0})
        self.assertEqual(deliver_report("   \n  "), {"sent": 0, "failed": 0})

    def test_placeholder_token_is_noop(self) -> None:
        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = True
            mock_config.TELEGRAM_BOT_TOKEN = "your-bot-token"

            with self.assertLogs("pipeline.delivery", level="WARNING"):
                result = deliver_report("# report body")

        self.assertEqual(result, {"sent": 0, "failed": 0})

    def test_dry_run_is_success_without_http(self) -> None:
        with patch("pipeline.delivery.requests.post") as mock_post:
            result = deliver_report("# report body", test_mode=True)
        mock_post.assert_not_called()
        self.assertEqual(result, {"sent": 1, "failed": 0})

    @patch("pipeline.delivery.requests.post")
    def test_send_failure_returns_failed_one(self, mock_post) -> None:
        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.text = "Unauthorized"
        unauthorized.headers = {}
        mock_post.return_value = unauthorized

        with patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            result = deliver_report("# report body")

        self.assertEqual(result, {"sent": 0, "failed": 1})

    def test_report_body_sent_without_parse_mode(self) -> None:
        """Sonnet's ``**bold**`` would be rejected by Telegram Markdown v1."""

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"ok": true}'
        ok_resp.headers = {}

        with patch("pipeline.delivery.requests.post", return_value=ok_resp) as mock_post, \
                patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            result = deliver_report("Plain **bold** body.")

        self.assertEqual(result, {"sent": 1, "failed": 0})
        self.assertEqual(mock_post.call_count, 1)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["text"], "Plain **bold** body.")
        self.assertNotIn("parse_mode", payload)

    def test_long_report_is_chunked_under_limit(self) -> None:
        """A 6k-char report gets split into multiple ≤4000-char sends."""

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = '{"ok": true}'
        ok_resp.headers = {}

        # Build a 6k-char body with paragraph boundaries so chunking has
        # clean split points to work with.
        paragraph = ("x" * 400 + "\n\n")  # ~402 chars
        long_report = paragraph * 15  # ~6030 chars

        with patch("pipeline.delivery.requests.post", return_value=ok_resp) as mock_post, \
                patch("pipeline.delivery._rate_limit"), \
                patch("pipeline.delivery.config") as mock_config:
            mock_config.is_test_mode.return_value = False
            mock_config.DRY_RUN = False
            mock_config._is_placeholder.return_value = False
            mock_config.TELEGRAM_BOT_TOKEN = "real-token"
            mock_config.TELEGRAM_CHANNEL_ID = "-100123"

            result = deliver_report(long_report)

        self.assertGreater(mock_post.call_count, 1)
        self.assertEqual(result["sent"], mock_post.call_count)
        self.assertEqual(result["failed"], 0)
        # Every chunk must stay under Telegram's hard cap.
        for call in mock_post.call_args_list:
            self.assertLessEqual(len(call.kwargs["json"]["text"]), _TELEGRAM_MESSAGE_LIMIT)


class ChunkTextTests(unittest.TestCase):
    """Direct coverage for the `_chunk_text` helper used by deliver_report."""

    def test_short_text_returns_single_chunk(self) -> None:
        self.assertEqual(_chunk_text("hello world", 4000), ["hello world"])

    def test_prefers_paragraph_boundary(self) -> None:
        a = "a" * 100
        b = "b" * 100
        text = f"{a}\n\n{b}"
        chunks = _chunk_text(text, 150)
        self.assertEqual(chunks[0], a)
        self.assertEqual(chunks[1], b)

    def test_falls_back_to_single_newline(self) -> None:
        a = "a" * 100
        b = "b" * 100
        text = f"{a}\n{b}"
        chunks = _chunk_text(text, 150)
        self.assertEqual(chunks[0], a)
        self.assertEqual(chunks[1], b)

    def test_hard_cut_when_no_whitespace(self) -> None:
        text = "x" * 500
        chunks = _chunk_text(text, 100)
        self.assertEqual(len(chunks), 5)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 100)
        self.assertEqual("".join(chunks), text)

    def test_every_chunk_under_limit(self) -> None:
        paragraph = ("word " * 80).strip() + "\n\n"  # ~400 chars
        text = paragraph * 20
        chunks = _chunk_text(text, 1000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1000)


if __name__ == "__main__":
    unittest.main()
