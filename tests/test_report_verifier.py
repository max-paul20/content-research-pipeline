"""Unit tests for the Gemini Flash-Lite report-quality verifier."""

import json
import unittest
from unittest.mock import MagicMock, patch

from pipeline import report_verifier
from pipeline.report_verifier import _normalize_verdict, verify_report


SAMPLE_ANALYSIS = {
    "engagement": {"topPerformers": [], "engagementPatterns": {}},
    "trends": {"emergingTrends": [], "fadingTrends": []},
    "competitors": {"competitorInsights": [], "gapOpportunities": []},
    "contentThemes": {"contentThemes": [], "performanceByTheme": {}},
}

SAMPLE_REPORT = "# Unigliss Trend Radar\n\n## TL;DR\n- some body\n"

FAIL_OPEN = {"overallPass": True, "rules": [], "retryInstructions": None}


def _mock_response(raw_text: str) -> MagicMock:
    r = MagicMock()
    r.text = raw_text
    return r


class VerifyReportTests(unittest.IsolatedAsyncioTestCase):
    """Cover every branch of _verify_report_sync."""

    async def test_test_mode_fails_open_without_http(self) -> None:
        with patch("pipeline.report_verifier.call_gemini") as mock_call:
            result = await verify_report(SAMPLE_REPORT, SAMPLE_ANALYSIS, test_mode=True)
        mock_call.assert_not_called()
        self.assertEqual(result, FAIL_OPEN)

    async def test_missing_credentials_fails_open(self) -> None:
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=False), \
             patch("pipeline.report_verifier.call_gemini") as mock_call, \
             patch.object(report_verifier.config, "TEST_MODE", False):
            with self.assertLogs("pipeline.report_verifier", level="WARNING"):
                result = await verify_report(SAMPLE_REPORT, SAMPLE_ANALYSIS, test_mode=False)
        mock_call.assert_not_called()
        self.assertEqual(result, FAIL_OPEN)

    async def test_http_none_fails_open(self) -> None:
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=True), \
             patch("pipeline.report_verifier.call_gemini", return_value=None), \
             patch("pipeline.report_verifier.load_skill", return_value="SYSTEM"), \
             patch.object(report_verifier.config, "TEST_MODE", False):
            with self.assertLogs("pipeline.report_verifier", level="WARNING"):
                result = await verify_report(SAMPLE_REPORT, SAMPLE_ANALYSIS, test_mode=False)
        self.assertEqual(result, FAIL_OPEN)

    async def test_unparseable_response_fails_open(self) -> None:
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=True), \
             patch(
                 "pipeline.report_verifier.call_gemini",
                 return_value=_mock_response("garbage"),
             ), \
             patch("pipeline.report_verifier.load_skill", return_value="SYSTEM"), \
             patch.object(report_verifier.config, "TEST_MODE", False):
            with self.assertLogs("pipeline.report_verifier", level="WARNING"):
                result = await verify_report(SAMPLE_REPORT, SAMPLE_ANALYSIS, test_mode=False)
        self.assertEqual(result, FAIL_OPEN)

    async def test_empty_report_returns_explicit_fail(self) -> None:
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=True), \
             patch("pipeline.report_verifier.call_gemini") as mock_call, \
             patch.object(report_verifier.config, "TEST_MODE", False):
            result = await verify_report("", SAMPLE_ANALYSIS, test_mode=False)
        # Empty report is the one case that does NOT fail open.
        mock_call.assert_not_called()
        self.assertFalse(result["overallPass"])
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["id"], "non-empty-report")
        self.assertFalse(result["rules"][0]["pass"])
        self.assertIsInstance(result["retryInstructions"], str)
        self.assertIn("empty", result["retryInstructions"].lower())

    async def test_whitespace_only_report_returns_explicit_fail(self) -> None:
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=True), \
             patch("pipeline.report_verifier.call_gemini") as mock_call, \
             patch.object(report_verifier.config, "TEST_MODE", False):
            result = await verify_report("   \n  ", SAMPLE_ANALYSIS, test_mode=False)
        mock_call.assert_not_called()
        self.assertFalse(result["overallPass"])

    async def test_happy_path_returns_normalized_verdict(self) -> None:
        verdict_payload = {
            "overallPass": True,
            "rules": [
                {"id": "r1", "pass": True, "detail": "ok"},
                {"id": "r2", "pass": True, "detail": "ok"},
            ],
            "retryInstructions": None,
        }
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=True), \
             patch(
                 "pipeline.report_verifier.call_gemini",
                 return_value=_mock_response(json.dumps(verdict_payload)),
             ), \
             patch("pipeline.report_verifier.load_skill", return_value="SYSTEM"), \
             patch.object(report_verifier.config, "TEST_MODE", False):
            result = await verify_report(SAMPLE_REPORT, SAMPLE_ANALYSIS, test_mode=False)
        self.assertEqual(result["overallPass"], True)
        self.assertEqual(len(result["rules"]), 2)
        self.assertIsNone(result["retryInstructions"])

    async def test_happy_path_fail_with_retry_instructions(self) -> None:
        verdict_payload = {
            "overallPass": False,
            "rules": [{"id": "r1", "pass": False, "detail": "section missing"}],
            "retryInstructions": "- Add the missing section",
        }
        with patch("pipeline.report_verifier.gemini_credentials_ok", return_value=True), \
             patch(
                 "pipeline.report_verifier.call_gemini",
                 return_value=_mock_response(json.dumps(verdict_payload)),
             ), \
             patch("pipeline.report_verifier.load_skill", return_value="SYSTEM"), \
             patch.object(report_verifier.config, "TEST_MODE", False):
            result = await verify_report(SAMPLE_REPORT, SAMPLE_ANALYSIS, test_mode=False)
        self.assertFalse(result["overallPass"])
        self.assertEqual(result["retryInstructions"], "- Add the missing section")


class NormalizeVerdictTests(unittest.TestCase):
    """The orchestrator depends on a consistent verdict shape."""

    def test_all_keys_pass_through(self) -> None:
        raw = {"overallPass": False, "rules": [{"id": "a", "pass": False}], "retryInstructions": "- do X"}
        self.assertEqual(
            _normalize_verdict(raw),
            {"overallPass": False, "rules": [{"id": "a", "pass": False}], "retryInstructions": "- do X"},
        )

    def test_missing_overallpass_inferred_from_rules_all_pass(self) -> None:
        raw = {"rules": [{"id": "a", "pass": True}, {"id": "b", "pass": True}]}
        self.assertTrue(_normalize_verdict(raw)["overallPass"])

    def test_missing_overallpass_inferred_from_rules_any_fail(self) -> None:
        raw = {"rules": [{"id": "a", "pass": True}, {"id": "b", "pass": False}]}
        self.assertFalse(_normalize_verdict(raw)["overallPass"])

    def test_missing_overallpass_and_empty_rules_defaults_to_true(self) -> None:
        self.assertTrue(_normalize_verdict({"rules": []})["overallPass"])
        self.assertTrue(_normalize_verdict({})["overallPass"])

    def test_blank_retry_instructions_coerced_to_none(self) -> None:
        self.assertIsNone(_normalize_verdict({"retryInstructions": ""})["retryInstructions"])
        self.assertIsNone(_normalize_verdict({"retryInstructions": "   "})["retryInstructions"])
        self.assertIsNone(_normalize_verdict({"retryInstructions": 42})["retryInstructions"])

    def test_rules_default_to_empty_list_when_missing(self) -> None:
        self.assertEqual(_normalize_verdict({})["rules"], [])
        self.assertEqual(_normalize_verdict({"rules": "not a list"})["rules"], [])


if __name__ == "__main__":
    unittest.main()
