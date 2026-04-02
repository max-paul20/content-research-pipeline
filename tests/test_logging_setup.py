"""Unit tests for startup logging configuration."""

import logging
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import logging_utils


class LoggingSetupTests(unittest.TestCase):
    """Verify console + rotating file logging is configured correctly."""

    def setUp(self) -> None:
        self.root_logger = logging.getLogger()
        self.original_handlers = self.root_logger.handlers[:]
        self.original_level = self.root_logger.level
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)
            handler.close()

    def tearDown(self) -> None:
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)
            handler.close()
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        self.root_logger.setLevel(self.original_level)

    def test_configure_logging_adds_console_and_rotating_file_handlers(self) -> None:
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "data" / "logs" / "pipeline.log"

            with patch.object(logging_utils, "_LOG_FILE", log_file):
                configured_path = logging_utils.configure_logging()
                logging.getLogger("test.logging").info("pipeline log smoke test")

                for handler in logging.getLogger().handlers:
                    handler.flush()

            handlers = logging.getLogger().handlers
            file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
            console_handlers = [
                h for h in handlers
                if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            ]

            self.assertEqual(configured_path, log_file)
            self.assertEqual(len(file_handlers), 1)
            self.assertEqual(file_handlers[0].maxBytes, 5 * 1024 * 1024)
            self.assertEqual(file_handlers[0].backupCount, 3)
            self.assertEqual(len(console_handlers), 1)
            self.assertTrue(log_file.exists())
            self.assertIn("pipeline log smoke test", log_file.read_text(encoding="utf-8"))

    def test_configure_logging_falls_back_to_console_if_file_handler_fails(self) -> None:
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "data" / "logs" / "pipeline.log"

            with patch.object(logging_utils, "_LOG_FILE", log_file), patch(
                "logging_utils.RotatingFileHandler",
                side_effect=OSError("disk full"),
            ), self.assertLogs("logging_utils", level="WARNING") as captured:
                configured_path = logging_utils.configure_logging()

            handlers = logging.getLogger().handlers
            file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
            console_handlers = [
                h for h in handlers
                if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            ]

            self.assertEqual(configured_path, log_file)
            self.assertEqual(file_handlers, [])
            self.assertEqual(len(console_handlers), 1)
            self.assertTrue(any("File logging disabled" in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
