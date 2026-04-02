"""Unit tests for delivered-script history persistence and filtering."""

import json
import logging
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.history import (
    filter_unscripted_posts,
    load_scripted_posts,
    record_scripted_posts,
    save_scripted_posts,
)


class ScriptedHistoryTests(unittest.TestCase):
    """Verify cross-run scripted-post dedup behavior."""

    def setUp(self) -> None:
        self.logger = logging.getLogger("test.history")

    def test_filter_unscripted_posts_skips_recent_scripted_posts(self) -> None:
        scripted_posts = {
            "tiktok:tk_001": {
                "first_delivered_at": "2026-03-30T12:00:00Z",
                "last_delivered_at": "2026-03-30T12:00:00Z",
                "platform": "tiktok",
                "post_id": "tk_001",
                "url": "https://www.tiktok.com/@creator/video/tk_001",
                "campuses": ["uofa"],
            }
        }
        posts = [
            {
                "platform": "tiktok",
                "post_id": "tk_001",
                "url": "https://www.tiktok.com/@creator/video/tk_001",
            },
            {
                "platform": "instagram",
                "post_id": "ig_001",
                "url": "https://www.instagram.com/reel/ig_001/",
            },
        ]

        filtered = filter_unscripted_posts(posts, scripted_posts, self.logger)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["post_id"], "ig_001")

    def test_load_scripted_posts_expires_entries_older_than_seven_days(self) -> None:
        with TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "scripted_posts.json"
            history_file.write_text(
                json.dumps(
                    {
                        "recent": {
                            "last_delivered_at": "2026-03-30T12:00:00Z",
                        },
                        "expired": {
                            "last_delivered_at": "2026-03-20T12:00:00Z",
                        },
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_scripted_posts(
                history_file,
                self.logger,
                now=datetime(2026, 3, 31, tzinfo=timezone.utc),
            )

        self.assertIn("recent", loaded)
        self.assertNotIn("expired", loaded)

    def test_record_and_save_scripted_posts_uses_source_identity(self) -> None:
        with TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "scripted_posts.json"
            scripted_posts = {}

            recorded = record_scripted_posts(
                scripted_posts,
                [
                    {
                        "campus": "uofa",
                        "source_platform": "tiktok",
                        "source_post_id": "tk_123",
                        "source_url": "https://www.tiktok.com/@creator/video/tk_123",
                    }
                ],
                self.logger,
                delivered_at="2026-03-31T12:00:00Z",
            )
            save_scripted_posts(history_file, scripted_posts, self.logger)
            reloaded = json.loads(history_file.read_text(encoding="utf-8"))

        self.assertEqual(recorded, 1)
        self.assertIn("tiktok:tk_123", reloaded)
        self.assertEqual(reloaded["tiktok:tk_123"]["campuses"], ["uofa"])


if __name__ == "__main__":
    unittest.main()
