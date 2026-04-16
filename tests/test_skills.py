"""Unit tests for the markdown skill loader."""

import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import skills
from pipeline.skills import SKILLS_DIR, load_skill


class LoadSkillTests(unittest.TestCase):
    """Verify the markdown skill loader."""

    def setUp(self) -> None:
        # Cache is module-level and other tests may have warmed it.
        skills._CACHE.clear()

    def test_load_skill_returns_file_body(self) -> None:
        text = load_skill("engagement-analysis")
        self.assertTrue(text)
        self.assertIn("engagement", text.lower())

    def test_load_skill_caches_after_first_read(self) -> None:
        real_read_text = Path.read_text
        call_counter = {"n": 0}

        def counting_read_text(self, *args, **kwargs):
            call_counter["n"] += 1
            return real_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", counting_read_text):
            first = load_skill("engagement-analysis")
            second = load_skill("engagement-analysis")

        self.assertEqual(first, second)
        self.assertEqual(call_counter["n"], 1)

    def test_load_skill_missing_raises_filenotfounderror(self) -> None:
        with self.assertRaises(FileNotFoundError) as ctx:
            load_skill("definitely-not-a-real-skill")
        self.assertIn("definitely-not-a-real-skill.md", str(ctx.exception))

    def test_load_skill_returns_raw_body_including_frontmatter(self) -> None:
        # load_skill does not strip YAML frontmatter; the full body, including
        # the leading "---\nname: ...\n---" header, is passed to the model.
        text = load_skill("engagement-analysis")
        self.assertTrue(text.startswith("---"))
        self.assertIn("name: engagement-analysis", text)

    def test_skills_dir_points_at_repo_skills_folder(self) -> None:
        # Sanity check: if someone moves the folder, loader tests should fail fast.
        self.assertTrue(SKILLS_DIR.is_dir())
        self.assertTrue((SKILLS_DIR / "engagement-analysis.md").is_file())


if __name__ == "__main__":
    unittest.main()
