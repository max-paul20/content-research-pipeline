"""Unit tests for the Unigliss Trend Radar knowledge base prompts."""

import unittest

from pipeline import (
    SUPPORTED_CAMPUSES,
    SUPPORTED_OUTPUT_MODES,
    get_analyzer_prompt,
    get_script_generator_prompt,
)


class KnowledgeBasePromptTests(unittest.TestCase):
    """Verify public prompt helpers and guardrails."""

    def test_supported_options_are_exposed(self) -> None:
        self.assertEqual(SUPPORTED_CAMPUSES, ("uofa", "calpoly"))
        self.assertEqual(SUPPORTED_OUTPUT_MODES, ("brief", "telegram"))

    def test_analyzer_prompt_includes_required_platform_and_brand_knowledge(self) -> None:
        prompt = get_analyzer_prompt()

        self.assertIn("TikTok 2026 Algorithm Intelligence", prompt)
        self.assertIn("Instagram Reels 2026 Algorithm Intelligence", prompt)
        self.assertIn("follower-first testing", prompt)
        self.assertIn("completion rate around 70%", prompt)
        self.assertIn("Originality Score", prompt)
        self.assertIn("exactly one natural Unigliss moment", prompt)
        self.assertIn("## Platform Diagnosis", prompt)
        self.assertIn("## Unigliss Adaptation", prompt)

    def test_default_campus_context_includes_both_launch_campuses(self) -> None:
        prompt = get_script_generator_prompt()

        self.assertIn("Old Main", prompt)
        self.assertIn("Arizona Stadium", prompt)
        self.assertIn("Higuera St", prompt)
        self.assertIn("Mustang Memorial", prompt)
        self.assertIn("Choose the single best campus", prompt)

    def test_uofa_prompt_only_includes_uofa_context(self) -> None:
        prompt = get_script_generator_prompt(campus="uofa")

        self.assertIn("University of Arizona (uofa)", prompt)
        self.assertIn("Old Main", prompt)
        self.assertIn("4th Ave", prompt)
        self.assertNotIn("Higuera St", prompt)
        self.assertNotIn("Mustang Memorial", prompt)

    def test_calpoly_prompt_only_includes_calpoly_context(self) -> None:
        prompt = get_script_generator_prompt(campus="calpoly")

        self.assertIn("Cal Poly SLO (calpoly)", prompt)
        self.assertIn("Higuera St", prompt)
        self.assertIn("Learn by Doing", prompt)
        self.assertNotIn("Old Main", prompt)
        self.assertNotIn("Arizona Stadium", prompt)

    def test_brief_and_telegram_modes_enforce_different_output_shapes(self) -> None:
        brief_prompt = get_script_generator_prompt(output_mode="brief")
        telegram_prompt = get_script_generator_prompt(output_mode="telegram")

        self.assertIn("Return one markdown creative brief.", brief_prompt)
        self.assertIn("## Hook (First 3 Seconds)", brief_prompt)
        self.assertIn("Return one Telegram-ready creator script in compact markdown.", telegram_prompt)
        self.assertIn("Title:", telegram_prompt)
        self.assertNotEqual(brief_prompt, telegram_prompt)

    def test_invalid_campus_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_analyzer_prompt(campus="asu")

    def test_invalid_output_mode_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_script_generator_prompt(output_mode="sms")


if __name__ == "__main__":
    unittest.main()
