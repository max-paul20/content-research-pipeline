"""Unit tests for the Unigliss Trend Radar knowledge base prompts."""

import unittest

from pipeline import (
    SUPPORTED_CAMPUSES,
    get_gemini_analysis_prompt,
    get_sonnet_script_prompt,
)


class KnowledgeBasePromptTests(unittest.TestCase):
    """Verify public prompt helpers and guardrails."""

    def test_supported_campuses_exposed(self) -> None:
        self.assertEqual(SUPPORTED_CAMPUSES, ("uofa", "calpoly"))

    def test_gemini_analysis_prompt_includes_platform_knowledge(self) -> None:
        prompt = get_gemini_analysis_prompt()

        self.assertIn("TikTok 2026 Algorithm Intelligence", prompt)
        self.assertIn("Instagram Reels 2026 Algorithm Intelligence", prompt)
        self.assertIn("follower-first testing", prompt)
        self.assertIn("completion rate around 70%", prompt)
        self.assertIn("Originality Score", prompt)

    def test_gemini_analysis_prompt_specifies_json_schema(self) -> None:
        prompt = get_gemini_analysis_prompt()

        self.assertIn("virality_score", prompt)
        self.assertIn("engagement_velocity", prompt)
        self.assertIn("trend_type", prompt)
        self.assertIn("virality_reason", prompt)
        self.assertIn("audio_lifecycle", prompt)
        self.assertIn("relevance_score", prompt)
        self.assertIn("recommended_campus", prompt)
        self.assertIn("macro_beauty", prompt)
        self.assertIn("campus_specific", prompt)
        self.assertIn("audio_driven", prompt)
        self.assertIn("format_driven", prompt)
        self.assertIn("emerging", prompt)
        self.assertIn("saturated", prompt)
        self.assertIn("no_audio", prompt)

    def test_gemini_analysis_prompt_includes_strategy(self) -> None:
        prompt = get_gemini_analysis_prompt()

        self.assertIn("exactly one natural Unigliss moment", prompt)
        self.assertIn("Campus Context", prompt)

    def test_gemini_analysis_prompt_includes_both_campuses(self) -> None:
        prompt = get_gemini_analysis_prompt()

        self.assertIn("Old Main", prompt)
        self.assertIn("Higuera St", prompt)

    def test_sonnet_script_prompt_uofa_includes_uofa_context(self) -> None:
        prompt = get_sonnet_script_prompt("uofa")

        self.assertIn("University of Arizona (uofa)", prompt)
        self.assertIn("Old Main", prompt)
        self.assertIn("4th Ave", prompt)
        self.assertNotIn("Higuera St", prompt)
        self.assertNotIn("Mustang Memorial", prompt)

    def test_sonnet_script_prompt_calpoly_includes_calpoly_context(self) -> None:
        prompt = get_sonnet_script_prompt("calpoly")

        self.assertIn("Cal Poly SLO (calpoly)", prompt)
        self.assertIn("Higuera St", prompt)
        self.assertIn("Learn by Doing", prompt)
        self.assertNotIn("Old Main", prompt)
        self.assertNotIn("Arizona Stadium", prompt)

    def test_sonnet_script_prompt_includes_format_instructions(self) -> None:
        prompt = get_sonnet_script_prompt("uofa")

        self.assertIn("HOOK", prompt)
        self.assertIn("KEY BEATS", prompt)
        self.assertIn("SUGGESTED DIALOGUE", prompt)
        self.assertIn("AUDIO", prompt)
        self.assertIn("HASHTAGS", prompt)
        self.assertIn("CAMPUS TIE-IN", prompt)

    def test_sonnet_script_prompt_includes_unigliss_mention_rule(self) -> None:
        prompt = get_sonnet_script_prompt("calpoly")

        self.assertIn("booking through Unigliss", prompt)

    def test_sonnet_script_prompt_includes_gen_z_tone(self) -> None:
        prompt = get_sonnet_script_prompt("uofa")

        self.assertIn("Gen Z", prompt)
        self.assertIn("NOT corporate", prompt)
        self.assertIn("NOT cringe", prompt)

    def test_invalid_campus_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_sonnet_script_prompt("asu")

        with self.assertRaises(ValueError):
            get_sonnet_script_prompt("")


if __name__ == "__main__":
    unittest.main()
