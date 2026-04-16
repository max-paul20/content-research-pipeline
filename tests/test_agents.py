"""Unit tests for the parallel Gemini lens agents."""

import json
import unittest
from unittest.mock import MagicMock, patch

from pipeline import agents
from pipeline.agents import (
    _run_agent,
    _safe_default,
    run_competitor_analyzer,
    run_content_classifier,
    run_engagement_analyzer,
    run_parallel_analysis,
    run_trend_detector,
)


def _mock_response(body: str) -> MagicMock:
    r = MagicMock()
    r.text = body
    return r


SAMPLE_POSTS = [
    {"post_id": "p1", "platform": "tiktok", "author": "a", "views": 10},
    {"post_id": "p2", "platform": "instagram", "author": "b", "views": 20},
]


class SafeDefaultShapeTests(unittest.TestCase):
    """Safe defaults are the contract all failure paths must honor."""

    def test_engagement_shape(self) -> None:
        self.assertEqual(_safe_default("engagement"), {"topPerformers": [], "engagementPatterns": {}})

    def test_trends_shape(self) -> None:
        self.assertEqual(_safe_default("trends"), {"emergingTrends": [], "fadingTrends": []})

    def test_competitors_shape(self) -> None:
        self.assertEqual(
            _safe_default("competitors"), {"competitorInsights": [], "gapOpportunities": []}
        )

    def test_content_themes_shape(self) -> None:
        self.assertEqual(
            _safe_default("contentThemes"),
            {"contentThemes": [], "performanceByTheme": {}},
        )

    def test_unknown_agent_returns_empty_dict(self) -> None:
        self.assertEqual(_safe_default("bogus"), {})


class RunAgentTests(unittest.TestCase):
    """Cover every branch in the shared _run_agent body."""

    @patch("pipeline.agents.call_gemini")
    def test_test_mode_returns_safe_default_without_http(
        self, mock_call: MagicMock
    ) -> None:
        result = _run_agent("engagement", "engagement-analysis", SAMPLE_POSTS, test_mode=True)
        self.assertEqual(result, _safe_default("engagement"))
        mock_call.assert_not_called()

    @patch("pipeline.agents.call_gemini")
    @patch("pipeline.agents.gemini_credentials_ok", return_value=False)
    def test_missing_credentials_returns_safe_default(
        self, _mock_creds: MagicMock, mock_call: MagicMock
    ) -> None:
        with self.assertLogs("pipeline.agents", level="WARNING"):
            result = _run_agent("trends", "trend-detection", SAMPLE_POSTS, test_mode=False)
        self.assertEqual(result, _safe_default("trends"))
        mock_call.assert_not_called()

    @patch("pipeline.agents.call_gemini")
    @patch("pipeline.agents.gemini_credentials_ok", return_value=True)
    def test_empty_posts_returns_safe_default(
        self, _mock_creds: MagicMock, mock_call: MagicMock
    ) -> None:
        result = _run_agent("competitors", "competitor-analysis", [], test_mode=False)
        self.assertEqual(result, _safe_default("competitors"))
        mock_call.assert_not_called()

    @patch("pipeline.agents.load_skill", return_value="system prompt")
    @patch("pipeline.agents.call_gemini", return_value=None)
    @patch("pipeline.agents.gemini_credentials_ok", return_value=True)
    def test_http_none_returns_safe_default(
        self, _mock_creds: MagicMock, _mock_call: MagicMock, _mock_skill: MagicMock
    ) -> None:
        result = _run_agent(
            "contentThemes", "content-classification", SAMPLE_POSTS, test_mode=False
        )
        self.assertEqual(result, _safe_default("contentThemes"))

    @patch("pipeline.agents.load_skill", return_value="system prompt")
    @patch("pipeline.agents.gemini_credentials_ok", return_value=True)
    @patch("pipeline.agents.call_gemini")
    def test_parse_failure_returns_safe_default(
        self, mock_call: MagicMock, _mock_creds: MagicMock, _mock_skill: MagicMock
    ) -> None:
        mock_call.return_value = _mock_response("this is not json")
        with self.assertLogs("pipeline.agents", level="WARNING"):
            result = _run_agent(
                "engagement", "engagement-analysis", SAMPLE_POSTS, test_mode=False
            )
        self.assertEqual(result, _safe_default("engagement"))

    @patch("pipeline.agents.load_skill", return_value="system prompt")
    @patch("pipeline.agents.gemini_credentials_ok", return_value=True)
    @patch("pipeline.agents.call_gemini")
    def test_success_returns_parsed_dict(
        self, mock_call: MagicMock, _mock_creds: MagicMock, _mock_skill: MagicMock
    ) -> None:
        payload = {"topPerformers": [{"post_id": "p1"}], "engagementPatterns": {"avg": 1}}
        mock_call.return_value = _mock_response(json.dumps(payload))
        result = _run_agent(
            "engagement", "engagement-analysis", SAMPLE_POSTS, test_mode=False
        )
        self.assertEqual(result, payload)

    @patch("pipeline.agents.load_skill")
    @patch("pipeline.agents.gemini_credentials_ok", return_value=True)
    @patch("pipeline.agents.call_gemini", return_value=None)
    def test_each_public_lens_loads_its_own_skill(
        self,
        _mock_call: MagicMock,
        _mock_creds: MagicMock,
        mock_skill: MagicMock,
    ) -> None:
        mock_skill.return_value = "system prompt"

        run_engagement_analyzer(SAMPLE_POSTS, test_mode=False)
        run_trend_detector(SAMPLE_POSTS, test_mode=False)
        run_competitor_analyzer(SAMPLE_POSTS, test_mode=False)
        run_content_classifier(SAMPLE_POSTS, test_mode=False)

        skills_loaded = [call.args[0] for call in mock_skill.call_args_list]
        self.assertEqual(
            skills_loaded,
            [
                "engagement-analysis",
                "trend-detection",
                "competitor-analysis",
                "content-classification",
            ],
        )


class RunParallelAnalysisTests(unittest.IsolatedAsyncioTestCase):
    """Verify the async merge + exception swallow contract."""

    async def test_merges_all_four_keys(self) -> None:
        def fake_run_agent(agent, _skill, _posts, _test_mode):
            return {f"{agent}-ok": True}

        with patch("pipeline.agents._run_agent", side_effect=fake_run_agent):
            merged = await run_parallel_analysis(SAMPLE_POSTS, test_mode=False)

        self.assertEqual(
            set(merged.keys()),
            {"engagement", "trends", "competitors", "contentThemes"},
        )
        self.assertEqual(merged["engagement"], {"engagement-ok": True})
        self.assertEqual(merged["trends"], {"trends-ok": True})

    async def test_one_agent_exception_does_not_block_others(self) -> None:
        def fake_run_agent(agent, _skill, _posts, _test_mode):
            if agent == "competitors":
                raise RuntimeError("lens boom")
            return {f"{agent}-ok": True}

        with patch("pipeline.agents._run_agent", side_effect=fake_run_agent):
            with self.assertLogs("pipeline.agents", level="WARNING"):
                merged = await run_parallel_analysis(SAMPLE_POSTS, test_mode=False)

        self.assertEqual(merged["engagement"], {"engagement-ok": True})
        self.assertEqual(merged["trends"], {"trends-ok": True})
        self.assertEqual(merged["contentThemes"], {"contentThemes-ok": True})
        # The failing agent falls back to its safe default.
        self.assertEqual(merged["competitors"], _safe_default("competitors"))

    async def test_test_mode_skips_http_and_returns_all_safe_defaults(self) -> None:
        with patch("pipeline.agents.call_gemini") as mock_call:
            merged = await run_parallel_analysis(SAMPLE_POSTS, test_mode=True)
        mock_call.assert_not_called()
        self.assertEqual(merged["engagement"], _safe_default("engagement"))
        self.assertEqual(merged["trends"], _safe_default("trends"))
        self.assertEqual(merged["competitors"], _safe_default("competitors"))
        self.assertEqual(merged["contentThemes"], _safe_default("contentThemes"))


if __name__ == "__main__":
    unittest.main()
