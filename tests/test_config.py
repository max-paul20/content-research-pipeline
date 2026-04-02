"""Unit tests for the central pipeline configuration module."""

import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional
from unittest.mock import patch


def reload_config(env: Optional[Dict[str, str]] = None):
    """Reload the config module with a controlled environment.

    ``load_dotenv`` is mocked so a developer's real ``.env`` file cannot
    bleed into tests that rely on specific default values.
    """

    with patch.dict(os.environ, env or {}, clear=True):
        with patch("dotenv.load_dotenv"):
            import pipeline.config as config

            return importlib.reload(config)


class ConfigTests(unittest.TestCase):
    """Verify defaults, validation, and test-mode behavior."""

    def test_default_values_are_sane(self) -> None:
        config = reload_config()

        self.assertEqual(config.GEMINI_MODEL, "gemini-2.5-flash-lite")
        self.assertEqual(config.SCRAPE_LIMIT, 20)
        self.assertAlmostEqual(config.VIRALITY_THRESHOLD, 0.7)
        self.assertEqual(config.MAX_GEMINI_CALLS_PER_RUN, 500)
        self.assertAlmostEqual(config.GEMINI_ANALYSIS_TEMPERATURE, 0.3)
        self.assertEqual(config.RUN_INTERVAL_HOURS, 6)
        self.assertEqual(config.SUPPORTED_CAMPUSES, ("uofa", "calpoly"))
        self.assertIsNone(config.DEFAULT_CAMPUS)
        self.assertEqual(config.LOG_DIR, config.DATA_DIR / "logs")
        self.assertEqual(config.SEEN_POSTS_FILE, config.DATA_DIR / "seen_posts.json")
        self.assertEqual(config.SCRIPTED_POSTS_FILE, config.DATA_DIR / "scripted_posts.json")
        self.assertFalse(config.DRY_RUN)
        self.assertFalse(config.TEST_MODE)
        self.assertEqual(config.ANTHROPIC_MODEL, "claude-sonnet-4-20250514")
        self.assertEqual(
            config.ANTHROPIC_API_URL, "https://api.anthropic.com/v1/messages"
        )
        self.assertEqual(config.SCRIPTS_PER_CAMPUS, 3)
        self.assertEqual(config.ANALYZER_TOP_N, 15)
        self.assertEqual(config.ANALYZER_MIN_SCORE, 50)

    def test_validate_config_catches_missing_and_placeholder_keys(self) -> None:
        config = reload_config(
            {
                "GEMINI_API_KEY": "your-key-here",
                "RAPIDAPI_KEY": "REPLACE_ME",
                "TELEGRAM_BOT_TOKEN": "",
                "TELEGRAM_CHANNEL_ID": "",
                "ANTHROPIC_API_KEY": "your-anthropic-key",
                "TEST_MODE": "false",
            }
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with patch.object(config, "DATA_DIR", temp_root / "data"), patch.object(
                config, "LOG_DIR", temp_root / "logs"
            ):
                status = config.validate_config()

        self.assertEqual(status["GEMINI_API_KEY"], "placeholder")
        self.assertEqual(status["RAPIDAPI_KEY"], "placeholder")
        self.assertEqual(status["TELEGRAM_BOT_TOKEN"], "missing")
        self.assertEqual(status["TELEGRAM_CHANNEL_ID"], "missing")
        self.assertEqual(status["ANTHROPIC_API_KEY"], "placeholder")

    def test_all_placeholder_patterns_are_caught(self) -> None:
        """Every entry in _PLACEHOLDER_VALUES must resolve to 'placeholder' status."""

        placeholder_values = [
            "your-key-here",
            "your-anthropic-key",
            "replace_me",
            "replace-me",
            "your-token-here",
            "your-channel-id",
            "your-bot-token",
            "changeme",
            "todo",
            "null",
            "none",
            # Case-insensitive variants
            "REPLACE_ME",
            "REPLACE-ME",
            "YOUR-KEY-HERE",
            "ChangeME",
            # Padded variants (stripped by _get_env_str)
            "  your-key-here  ",
            "  replace_me  ",
        ]

        for placeholder in placeholder_values:
            with self.subTest(placeholder=placeholder):
                config = reload_config(
                    {
                        "GEMINI_API_KEY": placeholder,
                        "RAPIDAPI_KEY": "real-key",
                        "TELEGRAM_BOT_TOKEN": "real-token",
                        "TELEGRAM_CHANNEL_ID": "-100123",
                        "ANTHROPIC_API_KEY": "real-anthropic-key",
                        "TEST_MODE": "false",
                    }
                )
                with TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    with patch.object(config, "DATA_DIR", temp_root / "data"), patch.object(
                        config, "LOG_DIR", temp_root / "logs"
                    ):
                        status = config.validate_config()
                self.assertEqual(
                    status["GEMINI_API_KEY"],
                    "placeholder",
                    msg=f"Expected 'placeholder' for value {placeholder!r}",
                )

    def test_whitespace_only_key_is_caught_as_missing(self) -> None:
        """A whitespace-only env var is stripped to '' and reported as missing."""

        config = reload_config(
            {
                "GEMINI_API_KEY": "   ",
                "RAPIDAPI_KEY": "real-key",
                "TELEGRAM_BOT_TOKEN": "real-token",
                "TELEGRAM_CHANNEL_ID": "-100123",
                "ANTHROPIC_API_KEY": "real-anthropic-key",
                "TEST_MODE": "false",
            }
        )
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with patch.object(config, "DATA_DIR", temp_root / "data"), patch.object(
                config, "LOG_DIR", temp_root / "logs"
            ):
                status = config.validate_config()
        self.assertEqual(status["GEMINI_API_KEY"], "missing")

    def test_validate_config_passes_when_all_keys_are_set(self) -> None:
        config = reload_config(
            {
                "GEMINI_API_KEY": "gemini-real-key",
                "RAPIDAPI_KEY": "rapidapi-real-key",
                "TELEGRAM_BOT_TOKEN": "telegram-real-token",
                "TELEGRAM_CHANNEL_ID": "-1001111111111",
                "ANTHROPIC_API_KEY": "sk-ant-real-key",
            }
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with patch.object(config, "DATA_DIR", temp_root / "data"), patch.object(
                config, "LOG_DIR", temp_root / "logs"
            ):
                status = config.validate_config()

        self.assertEqual(status["GEMINI_API_KEY"], "ok")
        self.assertEqual(status["RAPIDAPI_KEY"], "ok")
        self.assertEqual(status["TELEGRAM_BOT_TOKEN"], "ok")
        self.assertEqual(status["TELEGRAM_CHANNEL_ID"], "ok")
        self.assertEqual(status["ANTHROPIC_API_KEY"], "ok")

    def test_validate_config_creates_directories(self) -> None:
        config = reload_config({"TEST_MODE": "true"})

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            data_dir = temp_root / "data"
            log_dir = temp_root / "logs"
            with patch.object(config, "DATA_DIR", data_dir), patch.object(config, "LOG_DIR", log_dir):
                status = config.validate_config()

            self.assertTrue(data_dir.exists())
            self.assertTrue(log_dir.exists())
            self.assertIn(status["DATA_DIR"], {"ok (exists)", "ok (created)"})
            self.assertIn(status["LOG_DIR"], {"ok (exists)", "ok (created)"})

    def test_test_mode_skips_all_api_key_checks(self) -> None:
        """TEST_MODE must cause every required API key to report 'skipped'."""

        config = reload_config({"TEST_MODE": "true"})

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with patch.object(config, "DATA_DIR", temp_root / "data"), patch.object(
                config, "LOG_DIR", temp_root / "logs"
            ):
                status = config.validate_config()

        for key in config._REQUIRED_API_KEYS:
            self.assertEqual(
                status[key],
                "skipped (TEST_MODE enabled)",
                msg=f"Expected '{key}' to be skipped in TEST_MODE",
            )

    def test_is_test_mode_behavior(self) -> None:
        config = reload_config({"TEST_MODE": "true"})
        self.assertTrue(config.is_test_mode())

        config = reload_config({"TEST_MODE": "false"})
        self.assertFalse(config.is_test_mode())

    def test_endpoint_dicts_have_expected_keys(self) -> None:
        config = reload_config()

        self.assertIn("trending", config.TIKTOK_ENDPOINTS)
        self.assertIn("hashtag", config.TIKTOK_ENDPOINTS)
        self.assertIn("audio", config.TIKTOK_ENDPOINTS)
        self.assertIn("reels", config.INSTAGRAM_ENDPOINTS)
        self.assertIn("hashtag", config.INSTAGRAM_ENDPOINTS)

        # All endpoint values must be non-empty strings
        for key, val in config.TIKTOK_ENDPOINTS.items():
            self.assertIsInstance(val, str, msg=f"TIKTOK_ENDPOINTS[{key!r}] is not a str")
            self.assertTrue(val, msg=f"TIKTOK_ENDPOINTS[{key!r}] is empty")
        for key, val in config.INSTAGRAM_ENDPOINTS.items():
            self.assertIsInstance(val, str, msg=f"INSTAGRAM_ENDPOINTS[{key!r}] is not a str")
            self.assertTrue(val, msg=f"INSTAGRAM_ENDPOINTS[{key!r}] is empty")

    def test_invalid_numeric_env_vars_fall_back_to_defaults(self) -> None:
        config = reload_config(
            {
                "SCRAPE_LIMIT": "not-a-number",
                "VIRALITY_THRESHOLD": "abc",
                "MAX_GEMINI_CALLS_PER_RUN": "!!",
                "GEMINI_ANALYSIS_TEMPERATURE": "cold",
                "SCRIPTS_PER_CAMPUS": "many",
                "ANALYZER_TOP_N": "lots",
                "ANALYZER_MIN_SCORE": "high",
            }
        )

        self.assertEqual(config.SCRAPE_LIMIT, 20)
        self.assertAlmostEqual(config.VIRALITY_THRESHOLD, 0.7)
        self.assertEqual(config.MAX_GEMINI_CALLS_PER_RUN, 500)
        self.assertAlmostEqual(config.GEMINI_ANALYSIS_TEMPERATURE, 0.3)
        self.assertEqual(config.SCRIPTS_PER_CAMPUS, 3)
        self.assertEqual(config.ANALYZER_TOP_N, 15)
        self.assertEqual(config.ANALYZER_MIN_SCORE, 50)


if __name__ == "__main__":
    unittest.main()
