import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gemma_console_gui.config import AppConfig
from src.gemma_console_gui.console_session import ConsoleConfig, ConsoleSessionError
from src.gemma_console_gui.database import ChatRepository
from src.gemma_console_gui.gui import MainWindow


class FakeConsole:
    def __init__(self) -> None:
        self.config = ConsoleConfig("/bin/echo", "/tmp/model.gguf", ctx_size=2048)
        self.prompts: list[str] = []
        self.stopped = False

    def start(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def stop_generation(self) -> None:
        self.stopped = True

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        for _ in range(20):
            if self.stopped:
                self.stopped = False
                raise ConsoleSessionError("Generation stopped.")
            time.sleep(0.005)
        return "assistant answer"


def process_events(app: QApplication, cycles: int = 80) -> None:
    for _ in range(cycles):
        app.processEvents()
        time.sleep(0.005)


class GuiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])

    def test_stop_then_next_send_works(self) -> None:
        console = FakeConsole()
        db_path = Path(tempfile.mkdtemp()) / "app.db"
        window = MainWindow(
            console,
            ChatRepository(str(db_path)),
            AppConfig(llama_cli_path="/bin/echo", model_path="/tmp/model.gguf"),
        )

        window.input_edit.setPlainText("first")
        window.on_send()
        process_events(self.app, 5)
        window.on_stop_generation()
        process_events(self.app)

        self.assertIn("Generation stopped.", window.chat_view.toPlainText())
        self.assertTrue(window.send_btn.isEnabled())

        window.input_edit.setPlainText("second")
        window.on_send()
        process_events(self.app)

        self.assertIn("assistant answer", window.chat_view.toPlainText())
        self.assertIn("[You]\nfirst", console.prompts[-1])
        self.assertIn("[You]\nsecond", console.prompts[-1])
        self.assertTrue(console.prompts[-1].endswith("[Gemma]"))

        window.close()
        process_events(self.app, 5)


if __name__ == "__main__":
    unittest.main()
