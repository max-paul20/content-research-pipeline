"""Unit tests for the pipeline orchestrator."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from pipeline.main import _load_cache, _normalize_campus, _save_cache, run_pipeline


class NormalizeCampusTests(unittest.TestCase):
    """Verify campus name mapping."""

    def test_arizona_maps_to_uofa(self) -> None:
        self.assertEqual(_normalize_campus("arizona"), "uofa")
        self.assertEqual(_normalize_campus("Arizona"), "uofa")
        self.assertEqual(_normalize_campus("uofa"), "uofa")

    def test_calpoly_maps_to_calpoly(self) -> None:
        self.assertEqual(_normalize_campus("calpoly"), "calpoly")
        self.assertEqual(_normalize_campus("cal_poly"), "calpoly")

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(_normalize_campus("asu"))
        self.assertIsNone(_normalize_campus(""))


class CacheTests(unittest.TestCase):
    """Verify post caching."""

    def test_save_and_load_roundtrip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "data" / "cached_posts.json"
            posts = [{"post_id": "p1", "caption": "test"}]

            with patch("pipeline.main._CACHE_FILE", cache_file):
                _save_cache(posts)
                loaded = _load_cache()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["post_id"], "p1")

    def test_load_missing_file_returns_empty(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "nonexistent.json"
            with patch("pipeline.main._CACHE_FILE", cache_file):
                result = _load_cache()
            self.assertEqual(result, [])

    def test_load_corrupt_file_returns_empty(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "bad.json"
            cache_file.write_text("{not valid json")
            with patch("pipeline.main._CACHE_FILE", cache_file):
                result = _load_cache()
            self.assertEqual(result, [])


class PipelineWiringTests(unittest.TestCase):
    """Verify pipeline stages are called in order."""

    @patch("pipeline.main.deliver_scripts")
    @patch("pipeline.main.generate_scripts")
    @patch("pipeline.main.analyze_posts")
    @patch("pipeline.main.scrape_instagram")
    @patch("pipeline.main.scrape_tiktok")
    @patch("pipeline.main.config")
    def test_dry_run_calls_all_stages(
        self, mock_config, mock_tt, mock_ig, mock_analyze, mock_gen, mock_deliver
    ) -> None:
        mock_config.validate_config.return_value = {"DATA_DIR": "ok (exists)", "LOG_DIR": "ok (exists)"}
        mock_config.DATA_DIR = Path("/tmp/test_data")
        mock_config.is_test_mode.return_value = False
        mock_config.DRY_RUN = False

        mock_tt.return_value = [{"post_id": "tk_001"}]
        mock_ig.return_value = [{"post_id": "ig_001"}]
        mock_analyze.return_value = [
            {"post_id": "tk_001", "composite_score": 80, "recommended_campus": "both"}
        ]
        mock_gen.return_value = [
            {"campus": "uofa", "brief": "test", "source_url": "", "generated_at": "", "trend_type": ""}
        ]
        mock_deliver.return_value = {"sent": 1, "failed": 0}

        with patch("pipeline.main._save_cache"):
            run_pipeline(dry_run=True)

        mock_tt.assert_called_once_with(test_mode=True)
        mock_ig.assert_called_once_with(test_mode=True)
        mock_analyze.assert_called_once()
        mock_gen.assert_called_once()
        mock_deliver.assert_called_once()

    @patch("pipeline.main.deliver_scripts")
    @patch("pipeline.main.generate_scripts")
    @patch("pipeline.main.analyze_posts")
    @patch("pipeline.main._load_cache")
    @patch("pipeline.main.config")
    def test_skip_scrape_loads_cache(
        self, mock_config, mock_load, mock_analyze, mock_gen, mock_deliver
    ) -> None:
        mock_config.validate_config.return_value = {"DATA_DIR": "ok (exists)", "LOG_DIR": "ok (exists)"}
        mock_config.is_test_mode.return_value = False
        mock_config.DRY_RUN = False

        mock_load.return_value = [{"post_id": "cached_001"}]
        mock_analyze.return_value = [
            {"post_id": "cached_001", "composite_score": 80, "recommended_campus": "both"}
        ]
        mock_gen.return_value = []
        mock_deliver.return_value = {"sent": 0, "failed": 0}

        run_pipeline(dry_run=True, skip_scrape=True)

        mock_load.assert_called_once()
        mock_analyze.assert_called_once()

    @patch("pipeline.main.deliver_scripts")
    @patch("pipeline.main.generate_scripts")
    @patch("pipeline.main.analyze_posts")
    @patch("pipeline.main.scrape_tiktok")
    @patch("pipeline.main.scrape_instagram")
    @patch("pipeline.main.config")
    def test_campus_filter_limits_output(
        self, mock_config, mock_ig, mock_tt, mock_analyze, mock_gen, mock_deliver
    ) -> None:
        mock_config.validate_config.return_value = {"DATA_DIR": "ok (exists)", "LOG_DIR": "ok (exists)"}
        mock_config.is_test_mode.return_value = False
        mock_config.DRY_RUN = False

        mock_tt.return_value = [{"post_id": "p1"}, {"post_id": "p2"}]
        mock_ig.return_value = []
        mock_analyze.return_value = [
            {"post_id": "p1", "composite_score": 80, "recommended_campus": "uofa"},
            {"post_id": "p2", "composite_score": 70, "recommended_campus": "calpoly"},
        ]
        mock_gen.return_value = [
            {"campus": "uofa", "brief": "az", "source_url": "", "generated_at": "", "trend_type": ""},
        ]
        mock_deliver.return_value = {"sent": 1, "failed": 0}

        with patch("pipeline.main._save_cache"):
            run_pipeline(dry_run=True, campus="arizona")

        # generate_scripts receives filtered analyzed posts (only uofa/both)
        gen_call_posts = mock_gen.call_args[0][0]
        for p in gen_call_posts:
            self.assertIn(p.get("recommended_campus"), ("uofa", "both"))
        self.assertEqual(mock_gen.call_args.kwargs["target_campus"], "uofa")

    @patch("pipeline.main.scrape_tiktok")
    @patch("pipeline.main.scrape_instagram")
    @patch("pipeline.main.config")
    def test_no_posts_exits_early(self, mock_config, mock_ig, mock_tt) -> None:
        mock_config.validate_config.return_value = {"DATA_DIR": "ok (exists)", "LOG_DIR": "ok (exists)"}
        mock_config.is_test_mode.return_value = False
        mock_config.DRY_RUN = False

        mock_tt.return_value = []
        mock_ig.return_value = []

        with patch("pipeline.main._save_cache"):
            # Should not raise
            run_pipeline(dry_run=True)


class CliSmokeTests(unittest.TestCase):
    """Verify the CLI entry points execute successfully in dry-run mode."""

    def test_root_main_dry_run_exits_zero(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "main.py", "--dry-run"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
