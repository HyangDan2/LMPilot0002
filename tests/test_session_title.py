import unittest

from src.gemma_console_gui.session_title import DEFAULT_SESSION_TITLE, derive_session_title


class SessionTitleTests(unittest.TestCase):
    def test_derive_session_title_uses_first_words(self) -> None:
        self.assertEqual(
            derive_session_title("Please explain streaming response parsing for local models."),
            "Please explain streaming response parsing for local models",
        )

    def test_derive_session_title_falls_back_for_empty_text(self) -> None:
        self.assertEqual(derive_session_title(" \n "), DEFAULT_SESSION_TITLE)

    def test_derive_session_title_limits_length(self) -> None:
        title = derive_session_title("word " * 30, max_words=20, max_chars=18)

        self.assertLessEqual(len(title), 18)
        self.assertTrue(title.startswith("word word word"))


if __name__ == "__main__":
    unittest.main()
