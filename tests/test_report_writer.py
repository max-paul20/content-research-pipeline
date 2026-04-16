"""Unit tests for the Claude Sonnet insight-report writer."""

import json
import unittest
from unittest.mock import MagicMock, patch

from pipeline import report_writer
from pipeline.report_writer import _FALLBACK_REPORT, generate_report


SAMPLE_ANALYSIS = {
    "engagement": {"topPerformers": [{"post_id": "p1"}, {"post_id": "p2"}], "engagementPatterns": {}},
    "trends": {"emergingTrends": [{"name": "t1"}], "fadingTrends": []},
    "competitors": {"competitorInsights": [{"brand": "x"}], "gapOpportunities": []},
    "contentThemes": {"contentThemes": [{"label": "skincare"}], "performanceByTheme": {}},
}


def _anthropic_ok_text(body: str) -> str:
    return json.dumps({"content": [{"type": "text", "text": body}]})


def _mock_response(raw_text: str) -> MagicMock:
    r = MagicMock()
    r.text = raw_text
    return r


def _capture_posted_payload() -> tuple[MagicMock, dict]:
    """Return a mock for request_with_retries plus a dict populated on call."""

    captured: dict = {}

    def fake_retry(requester, **_kwargs):
        with patch("pipeline.report_writer.requests.post") as mock_post:
            mock_post.return_value = _mock_response(_anthropic_ok_text("# body"))
            requester()
            captured["args"] = mock_post.call_args
        return mock_post.return_value

    mock_retry = MagicMock(side_effect=fake_retry)
    return mock_retry, captured


class GenerateReportTests(unittest.IsolatedAsyncioTestCase):
    """Verify every branch of generate_report."""

    async def test_test_mode_returns_mock_without_http(self) -> None:
        with patch("pipeline.report_writer.request_with_retries") as mock_retry:
            text = await generate_report(SAMPLE_ANALYSIS, test_mode=True)
        mock_retry.assert_not_called()
        self.assertIn("mock cycle", text)
        # Mock report cites the input counts.
        self.assertIn("Engagement top performers: 2", text)
        self.assertIn("Emerging trends: 1", text)

    async def test_placeholder_key_returns_fallback_without_http(self) -> None:
        with patch("pipeline.report_writer.request_with_retries") as mock_retry, \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "your-anthropic-key"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            with self.assertLogs("pipeline.report_writer", level="WARNING"):
                text = await generate_report(SAMPLE_ANALYSIS, test_mode=False)
        mock_retry.assert_not_called()
        self.assertEqual(text, _FALLBACK_REPORT)

    async def test_http_none_returns_fallback(self) -> None:
        with patch("pipeline.report_writer.request_with_retries", return_value=None), \
             patch("pipeline.report_writer.load_skill", return_value="SYSTEM"), \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "sk-ant-real-looking"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            text = await generate_report(SAMPLE_ANALYSIS, test_mode=False)
        self.assertEqual(text, _FALLBACK_REPORT)

    async def test_parse_failure_returns_fallback(self) -> None:
        with patch(
            "pipeline.report_writer.request_with_retries",
            return_value=_mock_response("not-json"),
        ), patch("pipeline.report_writer.load_skill", return_value="SYSTEM"), \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "sk-ant-real-looking"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            with self.assertLogs("pipeline.report_writer", level="WARNING"):
                text = await generate_report(SAMPLE_ANALYSIS, test_mode=False)
        self.assertEqual(text, _FALLBACK_REPORT)

    async def test_success_returns_extracted_text(self) -> None:
        with patch(
            "pipeline.report_writer.request_with_retries",
            return_value=_mock_response(_anthropic_ok_text("# My Report\n\nBody")),
        ), patch("pipeline.report_writer.load_skill", return_value="SYSTEM"), \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "sk-ant-real-looking"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            text = await generate_report(SAMPLE_ANALYSIS, test_mode=False)
        self.assertEqual(text, "# My Report\n\nBody")

    async def test_system_block_carries_cache_control_ephemeral(self) -> None:
        mock_retry, captured = _capture_posted_payload()
        with patch("pipeline.report_writer.request_with_retries", mock_retry), \
             patch("pipeline.report_writer.load_skill", return_value="SYSTEM"), \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "sk-ant-real-looking"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            await generate_report(SAMPLE_ANALYSIS, test_mode=False)

        payload = captured["args"].kwargs["json"]
        system = payload["system"]
        self.assertEqual(len(system), 1)
        self.assertEqual(system[0]["type"], "text")
        self.assertEqual(system[0]["text"], "SYSTEM")
        self.assertEqual(system[0]["cache_control"], {"type": "ephemeral"})

    async def test_retry_instructions_appended_to_user_turn(self) -> None:
        mock_retry, captured = _capture_posted_payload()
        with patch("pipeline.report_writer.request_with_retries", mock_retry), \
             patch("pipeline.report_writer.load_skill", return_value="SYSTEM"), \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "sk-ant-real-looking"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            await generate_report(
                SAMPLE_ANALYSIS,
                test_mode=False,
                retry_instructions="- fix section 3",
            )

        user_content = captured["args"].kwargs["json"]["messages"][0]["content"]
        self.assertIn("## retry_instructions", user_content)
        self.assertIn("- fix section 3", user_content)

    async def test_no_retry_instructions_absent_from_user_turn(self) -> None:
        mock_retry, captured = _capture_posted_payload()
        with patch("pipeline.report_writer.request_with_retries", mock_retry), \
             patch("pipeline.report_writer.load_skill", return_value="SYSTEM"), \
             patch.object(report_writer.config, "ANTHROPIC_API_KEY", "sk-ant-real-looking"), \
             patch.object(report_writer.config, "TEST_MODE", False):
            await generate_report(SAMPLE_ANALYSIS, test_mode=False)

        user_content = captured["args"].kwargs["json"]["messages"][0]["content"]
        self.assertNotIn("## retry_instructions", user_content)


if __name__ == "__main__":
    unittest.main()
