"""Unit tests for the shared Gemini transport helpers."""

import json
import unittest
from unittest.mock import MagicMock, patch

from pipeline import gemini_utils
from pipeline.gemini_utils import (
    call_gemini,
    gemini_credentials_ok,
    parse_gemini_object,
)


def _candidates_wrap(inner_text: str) -> str:
    return json.dumps(
        {"candidates": [{"content": {"parts": [{"text": inner_text}]}}]}
    )


class ParseGeminiObjectTests(unittest.TestCase):
    """Verify every shape parse_gemini_object is expected to handle."""

    def test_parse_clean_json_object(self) -> None:
        self.assertEqual(parse_gemini_object('{"a": 1}'), {"a": 1})

    def test_parse_candidates_wrapped(self) -> None:
        raw = _candidates_wrap('{"emergingTrends": ["x"]}')
        self.assertEqual(parse_gemini_object(raw), {"emergingTrends": ["x"]})

    def test_parse_candidates_wrapped_with_code_fence_inside(self) -> None:
        raw = _candidates_wrap('```json\n{"a": 1}\n```')
        self.assertEqual(parse_gemini_object(raw), {"a": 1})

    def test_parse_markdown_code_fence(self) -> None:
        self.assertEqual(parse_gemini_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_parse_preamble_before_json(self) -> None:
        raw = 'Here you go: {"a": 1}'
        self.assertEqual(parse_gemini_object(raw), {"a": 1})

    def test_parse_truncated_json_returns_none(self) -> None:
        self.assertIsNone(parse_gemini_object('{"incomplete":'))

    def test_parse_wrong_shape_array_of_strings_returns_none(self) -> None:
        self.assertIsNone(parse_gemini_object('["a", "b"]'))

    def test_parse_array_of_dicts_returns_first_dict(self) -> None:
        # Documented fallback: a bare JSON array whose first element is a dict
        # collapses to that first dict so callers always get a mapping back.
        self.assertEqual(parse_gemini_object('[{"a": 1}, {"b": 2}]'), {"a": 1})

    def test_parse_empty_text_returns_none(self) -> None:
        self.assertIsNone(parse_gemini_object(""))

    def test_parse_whitespace_only_returns_none(self) -> None:
        self.assertIsNone(parse_gemini_object("   \n  "))


class GeminiCredentialsTests(unittest.TestCase):
    """Verify the credential guard."""

    def test_empty_returns_false(self) -> None:
        with patch.object(gemini_utils.config, "GEMINI_API_KEY", ""):
            self.assertFalse(gemini_credentials_ok())

    def test_placeholder_returns_false(self) -> None:
        with patch.object(gemini_utils.config, "GEMINI_API_KEY", "replace_me"):
            self.assertFalse(gemini_credentials_ok())

    def test_real_looking_key_returns_true(self) -> None:
        with patch.object(gemini_utils.config, "GEMINI_API_KEY", "AIzaSyFakeRealLookingKey"):
            self.assertTrue(gemini_credentials_ok())


class CallGeminiTests(unittest.TestCase):
    """Verify the thin HTTP wrapper around request_with_retries."""

    @patch("pipeline.gemini_utils.request_with_retries")
    def test_success_returns_response_and_posts_json_mode(
        self, mock_retry: MagicMock
    ) -> None:
        captured = {}

        def _run(requester, **_kwargs):
            # Capture the payload the lambda would send without actually calling it.
            with patch("pipeline.gemini_utils.requests.post") as mock_post:
                mock_post.return_value = MagicMock()
                requester()
                captured["args"] = mock_post.call_args
            return mock_post.return_value

        mock_retry.side_effect = _run

        response = call_gemini("sys", "user", operation="unit test")
        self.assertIsNotNone(response)

        call = captured["args"]
        url = call.args[0]
        payload = call.kwargs["json"]
        self.assertIn(gemini_utils.config.GEMINI_API_ENDPOINT, url)
        self.assertEqual(
            payload["generationConfig"]["responseMimeType"], "application/json"
        )
        self.assertEqual(
            payload["systemInstruction"]["parts"][0]["text"], "sys"
        )
        self.assertEqual(
            payload["contents"][0]["parts"][0]["text"], "user"
        )

    @patch("pipeline.gemini_utils.request_with_retries")
    def test_http_none_returns_none(self, mock_retry: MagicMock) -> None:
        mock_retry.return_value = None
        self.assertIsNone(call_gemini("sys", "user", operation="unit test"))


if __name__ == "__main__":
    unittest.main()
