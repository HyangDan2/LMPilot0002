import tempfile
import unittest
from pathlib import Path

from src.gui.database import ChatRepository


class ChatRepositoryTests(unittest.TestCase):
    def test_update_session_title(self) -> None:
        db_path = Path(tempfile.mkdtemp()) / "chat.db"
        repository = ChatRepository(str(db_path))
        session_id = repository.create_session()

        repository.update_session_title(session_id, "Helpful title")

        self.assertEqual(repository.get_session_title(session_id), "Helpful title")
        self.assertEqual(repository.list_sessions()[0]["title"], "Helpful title")

    def test_update_session_workspace_folder(self) -> None:
        db_path = Path(tempfile.mkdtemp()) / "chat.db"
        repository = ChatRepository(str(db_path))
        session_id = repository.create_session()

        repository.update_session_workspace_folder(session_id, "/tmp/workspace")

        self.assertEqual(repository.get_session_workspace_folder(session_id), "/tmp/workspace")
        self.assertEqual(repository.list_sessions()[0]["workspace_folder"], "/tmp/workspace")

        reopened = ChatRepository(str(db_path))
        self.assertEqual(reopened.get_session_workspace_folder(session_id), "/tmp/workspace")

        reopened.update_session_workspace_folder(session_id, None)
        self.assertEqual(reopened.get_session_workspace_folder(session_id), "")


if __name__ == "__main__":
    unittest.main()
