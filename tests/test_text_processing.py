import unittest

from src.gemma_console_gui.gui import normalize_text_for_display
from src.gemma_console_gui.token_handler import (
    handle_token_limits,
    limit_prompt_text,
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
        self.assertEqual(limit_prompt_text("abcdef", max_tokens=10, max_chars=3), "abc")

    def test_prompt_normalization_collapses_multiline_paste(self) -> None:
        text = "Summarize this\n\n첫 문장입니다.\n￼\n둘째 문장입니다."
        self.assertEqual(normalize_prompt_text(text), "Summarize this 첫 문장입니다. 둘째 문장입니다.")
        self.assertEqual(limit_prompt_text(text, max_tokens=20), "Summarize this 첫 문장입니다. 둘째 문장입니다.")

    def test_prompt_token_budget_reserves_response_space(self) -> None:
        self.assertEqual(prompt_token_budget(128, 32), 96)
        self.assertEqual(prompt_token_budget(4, 32), 1)


if __name__ == "__main__":
    unittest.main()
