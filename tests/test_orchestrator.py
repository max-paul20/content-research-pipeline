"""Unit tests for the async orchestrator's verify-retry loop.

These tests exercise :func:`pipeline.main.run_pipeline_async` via the sync
wrapper :func:`pipeline.main.run_pipeline`. They are kept separate from
``tests/test_main.py`` (whose 13 sync cases must stay unchanged) so they
can focus on the parts introduced by Phase 4: parallel analysis +
generation, the verifier verdict, and the single-retry regeneration.
"""

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.main import run_pipeline


def _analysis_dict() -> dict:
    return {
        "engagement": {"topPerformers": [], "engagementPatterns": {}},
        "trends": {"emergingTrends": [], "fadingTrends": []},
        "competitors": {"competitorInsights": [], "gapOpportunities": []},
        "contentThemes": {"contentThemes": [], "performanceByTheme": {}},
    }


def _analyzed_posts() -> list:
    return [
        {"post_id": "p1", "composite_score": 80, "recommended_campus": "both"}
    ]


def _scripts() -> list:
    return [
        {
            "campus": "uofa",
            "brief": "test",
            "source_url": "",
            "generated_at": "",
            "trend_type": "",
        }
    ]


class VerifyRetryLoopTests(unittest.TestCase):
    """Cover the three verdict outcomes and the regeneration contract."""

    def _patch_all(
        self,
        *,
        verify_result: dict,
        generate_report_side_effect=None,
    ):
        """Build the stack of mocks every orchestrator test needs.

        Patches are applied at ``pipeline.main.*`` module level (same
        strategy as ``tests/test_main.py``) so they intercept even when the
        async body dispatches the sync stages through ``asyncio.to_thread``.
        """

        config_mock = MagicMock()
        config_mock.validate_config.return_value = {
            "DATA_DIR": "ok (exists)",
            "LOG_DIR": "ok (exists)",
        }
        config_mock.DATA_DIR = Path("/tmp/test_data")
        config_mock.is_test_mode.return_value = False
        config_mock.DRY_RUN = False

        generate_report_mock = AsyncMock(
            side_effect=generate_report_side_effect or ["# first report", "# regenerated report"]
        )
        verify_mock = AsyncMock(return_value=verify_result)
        run_parallel_mock = AsyncMock(return_value=_analysis_dict())

        patches = [
            patch("pipeline.main.config", config_mock),
            patch("pipeline.main.scrape_tiktok", return_value=[{"post_id": "t1"}]),
            patch("pipeline.main.scrape_instagram", return_value=[]),
            patch("pipeline.main.analyze_posts", return_value=_analyzed_posts()),
            patch("pipeline.main.run_parallel_analysis", run_parallel_mock),
            patch("pipeline.main.generate_report", generate_report_mock),
            patch("pipeline.main.generate_scripts", return_value=_scripts()),
            patch("pipeline.main.verify_report", verify_mock),
            patch(
                "pipeline.main.deliver_scripts",
                return_value={"sent": 1, "failed": 0, "delivered_scripts": []},
            ),
            patch("pipeline.main.deliver_report", return_value={"sent": 1, "failed": 0}),
            patch("pipeline.main._save_cache"),
        ]
        return patches, generate_report_mock, verify_mock

    def test_verdict_pass_delivers_once_no_regeneration(self) -> None:
        patches, gen_mock, verify_mock = self._patch_all(
            verify_result={"overallPass": True, "rules": [], "retryInstructions": None},
        )
        for p in patches:
            p.start()
        try:
            run_pipeline(dry_run=True)
        finally:
            for p in reversed(patches):
                p.stop()

        # Report is generated exactly once; verifier is called exactly once.
        self.assertEqual(gen_mock.await_count, 1)
        self.assertEqual(verify_mock.await_count, 1)

    def test_verdict_fail_with_instructions_regenerates_once(self) -> None:
        patches, gen_mock, verify_mock = self._patch_all(
            verify_result={
                "overallPass": False,
                "rules": [{"id": "r1", "pass": False}],
                "retryInstructions": "- fix X",
            },
        )
        for p in patches:
            p.start()
        try:
            run_pipeline(dry_run=True)
        finally:
            for p in reversed(patches):
                p.stop()

        self.assertEqual(gen_mock.await_count, 2)
        # Verifier is NOT called a second time — regeneration delivers regardless.
        self.assertEqual(verify_mock.await_count, 1)
        # Second generate_report call carries the verifier's retry instructions.
        second_call = gen_mock.await_args_list[1]
        self.assertEqual(second_call.kwargs.get("retry_instructions"), "- fix X")

    def test_verdict_fail_without_instructions_skips_regeneration(self) -> None:
        patches, gen_mock, verify_mock = self._patch_all(
            verify_result={
                "overallPass": False,
                "rules": [{"id": "r1", "pass": False}],
                "retryInstructions": None,
            },
        )
        for p in patches:
            p.start()
        try:
            run_pipeline(dry_run=True)
        finally:
            for p in reversed(patches):
                p.stop()

        # Both conditions must be true to regenerate; missing instructions skips.
        self.assertEqual(gen_mock.await_count, 1)
        self.assertEqual(verify_mock.await_count, 1)

    def test_regenerated_report_is_delivered(self) -> None:
        patches, gen_mock, _verify_mock = self._patch_all(
            verify_result={
                "overallPass": False,
                "rules": [],
                "retryInstructions": "- fix X",
            },
            generate_report_side_effect=["# first", "# regenerated"],
        )
        # Capture the text passed to deliver_report.
        deliver_report_patch = patch("pipeline.main.deliver_report")
        for p in patches:
            p.start()
        deliver_report_mock = deliver_report_patch.start()
        deliver_report_mock.return_value = {"sent": 1, "failed": 0}
        try:
            run_pipeline(dry_run=True)
        finally:
            deliver_report_patch.stop()
            for p in reversed(patches):
                p.stop()

        self.assertEqual(gen_mock.await_count, 2)
        deliver_report_mock.assert_called_once()
        delivered_text = deliver_report_mock.call_args.args[0]
        self.assertEqual(delivered_text, "# regenerated")

    def test_report_delivery_logged_but_not_in_stats_delivered(self) -> None:
        patches, _gen_mock, _verify_mock = self._patch_all(
            verify_result={"overallPass": True, "rules": [], "retryInstructions": None},
        )
        # Bump deliver_scripts to return 2 sent so we can tell the two counts apart.
        deliver_scripts_patch = patch(
            "pipeline.main.deliver_scripts",
            return_value={"sent": 2, "failed": 0, "delivered_scripts": []},
        )
        deliver_report_patch = patch(
            "pipeline.main.deliver_report",
            return_value={"sent": 1, "failed": 0},
        )
        # Pop the placeholders we registered in _patch_all so the more specific
        # patches below apply cleanly.
        patches = [p for p in patches if p.attribute not in {"deliver_scripts", "deliver_report"}]

        for p in patches:
            p.start()
        deliver_scripts_patch.start()
        deliver_report_patch.start()
        try:
            with self.assertLogs("pipeline.main", level="INFO") as captured:
                run_pipeline(dry_run=True)
        finally:
            deliver_report_patch.stop()
            deliver_scripts_patch.stop()
            for p in reversed(patches):
                p.stop()

        self.assertTrue(
            any(
                "delivered=2" in line and "errors=0" in line
                for line in captured.output
            ),
            msg=f"summary line missing; log was:\n{chr(10).join(captured.output)}",
        )
        self.assertTrue(
            any("Report delivery: 1 sent, 0 failed." in line for line in captured.output),
            msg=f"report delivery line missing; log was:\n{chr(10).join(captured.output)}",
        )


if __name__ == "__main__":
    unittest.main()
