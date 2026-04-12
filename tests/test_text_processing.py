import unittest

from src.gemma_console_gui.gui import normalize_text_for_display
from src.gemma_console_gui.token_handler import (
    build_model_prompt,
    handle_token_limits,
    normalize_prompt_text,
    prompt_token_budget,
    truncate_text_to_char_budget,
    truncate_text_to_token_budget,
)


class TextProcessingTests(unittest.TestCase):
    def test_unicode_escape_normalization_preserves_korean(self) -> None:
        text = "한글 " + chr(92) + "u003c ok"
        self.assertEqual(normalize_text_for_display(text), "한글 < ok")

    def test_slash_unicode_escape_is_normalized(self) -> None:
        self.assertEqual(normalize_text_for_display("/u003c"), "<")

    def test_token_limit_keeps_newest_turns(self) -> None:
        conversation = ["one two", "three four five", "six"]
        self.assertEqual(handle_token_limits(conversation, 4), ["three four five", "six"])

    def test_token_limit_truncates_overlong_turn(self) -> None:
        self.assertEqual(truncate_text_to_token_budget("one two three", 2), "one two")
        self.assertEqual(handle_token_limits(["one two three four"], 2), ["one two"])

    def test_char_limit_truncates_text_without_spaces(self) -> None:
        self.assertEqual(truncate_text_to_char_budget("abcdef", 3), "abc")
        self.assertEqual(build_model_prompt([], "abcdef", max_tokens=10, max_chars=18), "[You]\nabc\n\n[Gemma]")
        self.assertEqual(build_model_prompt([], "abcdef", max_tokens=10, max_chars=25), "[You]\nabcdef\n\n[Gemma]")

    def test_prompt_normalization_preserves_multiline_paste(self) -> None:
        text = "Summarize this\n\n첫 문장입니다.\n￼\n둘째 문장입니다."
        self.assertEqual(normalize_prompt_text(text), "Summarize this\n\n첫 문장입니다.\n\n둘째 문장입니다.")

    def test_prompt_normalization_preserves_code_structure(self) -> None:
        text = "Traceback:\r\n  File \"app.py\", line 1\r\n    raise ValueError()\r\nValueError"
        self.assertEqual(
            normalize_prompt_text(text),
            "Traceback:\n  File \"app.py\", line 1\n    raise ValueError()\nValueError",
        )

    def test_build_model_prompt_includes_history(self) -> None:
        messages = [
            {"role": "user", "content": "Here is some code:\n    print('hi')"},
            {"role": "assistant", "content": "It prints hi."},
        ]
        prompt = build_model_prompt(messages, "Explain the previous code again.", 100)
        self.assertIn("[You]\nHere is some code:\n    print('hi')", prompt)
        self.assertIn("[Gemma]\nIt prints hi.", prompt)
        self.assertTrue(prompt.endswith("[You]\nExplain the previous code again.\n\n[Gemma]"))

    def test_build_model_prompt_trims_oldest_turns_first(self) -> None:
        messages = [
            {"role": "user", "content": "old user context " * 10},
            {"role": "assistant", "content": "old assistant context " * 10},
            {"role": "user", "content": "newer user"},
            {"role": "assistant", "content": "newer assistant"},
        ]
        prompt = build_model_prompt(messages, "current question", max_tokens=12)
        self.assertNotIn("old user context", prompt)
        self.assertNotIn("old assistant context", prompt)
        self.assertIn("newer assistant", prompt)
        self.assertIn("current question", prompt)
        self.assertTrue(prompt.endswith("[Gemma]"))

    def test_prompt_token_budget_reserves_response_space(self) -> None:
        self.assertEqual(prompt_token_budget(128, 32), 96)
        self.assertEqual(prompt_token_budget(4, 32), 1)


if __name__ == "__main__":
    unittest.main()
