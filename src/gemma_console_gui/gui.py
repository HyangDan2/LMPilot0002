from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QFont, QTextCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig
from .console_session import ConsoleSessionError, LlamaConsoleSession
from .database import ChatRepository
from .token_handler import limit_prompt_text, prompt_token_budget

UNICODE_ESCAPE_RE = re.compile(r'\\u[0-9a-fA-F]{4}|/u[0-9a-fA-F]{4}')


def normalize_text_for_display(text: str) -> str:
    if not isinstance(text, str):
        return str(text)

    def replace_escape(match: re.Match[str]) -> str:
        fixed = match.group(0).replace('/u', '\\u')
        try:
            return chr(int(fixed[2:], 16))
        except ValueError:
            return match.group(0)

    return UNICODE_ESCAPE_RE.sub(replace_escape, text)


def strip_unsupported_chars(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    return ''.join(ch for ch in text if ord(ch) <= 0xFFFF)


@dataclass
class ChatTask:
    session_id: int
    user_text: str


class ChatWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, console: LlamaConsoleSession, user_text: str) -> None:
        super().__init__()
        self.console = console
        self.user_text = user_text
        self.max_prompt_tokens = prompt_token_budget(console.config.ctx_size)

    @Slot()
    def run(self) -> None:
        try:
            limited_user_text = limit_prompt_text(self.user_text, self.max_prompt_tokens)
            answer = self.console.ask(limited_user_text)
            self.finished.emit(answer)
        except (ConsoleSessionError, Exception) as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, console: LlamaConsoleSession, repository: ChatRepository, app_config: AppConfig) -> None:
        super().__init__()
        self.console = console
        self.repository = repository
        self.app_config = app_config
        self.current_session_id: int | None = None
        self._worker_thread: QThread | None = None
        self._worker: ChatWorker | None = None
        self._generation_stop_requested = False

        self.setWindowTitle(app_config.window_title)
        self.resize(app_config.window_width, app_config.window_height)

        self.session_list = QListWidget()
        self.session_list.itemClicked.connect(self._on_session_selected)

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText('Type your message here...')
        self.input_edit.setFixedHeight(120)

        self.send_btn = QPushButton('Send')
        self.send_btn.clicked.connect(self.on_send)

        self.stop_btn = QPushButton('Stop')
        self.stop_btn.setDisabled(True)
        self.stop_btn.clicked.connect(self.on_stop_generation)

        self.new_chat_btn = QPushButton('New Chat')
        self.new_chat_btn.clicked.connect(self.on_new_chat)

        self.delete_chat_btn = QPushButton('Delete Chat')
        self.delete_chat_btn.clicked.connect(self._delete_current_chat)

        self.clear_view_btn = QPushButton('Clear View')
        self.clear_view_btn.clicked.connect(self._clear_view_only)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel('Sessions'))
        left_layout.addWidget(self.session_list)
        left_layout.addWidget(self.new_chat_btn)
        left_layout.addWidget(self.delete_chat_btn)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel('Chat'))
        right_layout.addWidget(self.chat_view, stretch=1)
        right_layout.addWidget(QLabel('Input'))
        right_layout.addWidget(self.input_edit)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.clear_view_btn)
        button_row.addWidget(self.stop_btn)
        button_row.addWidget(self.send_btn)
        right_layout.addLayout(button_row)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 780])

        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.addWidget(splitter)
        self.setCentralWidget(container)

        status = QStatusBar()
        self.setStatusBar(status)
        self._set_status('Starting console session...')

        self._init_console()
        self._reload_sessions()
        self._set_status('Idle')
        self._append_block('System', 'Select a session or click New Chat.')

        # Ctrl+Enter → Send
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input_edit)
        self.send_shortcut.activated.connect(self.on_send)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker_thread is not None and self._worker_thread.isRunning():
            self._generation_stop_requested = True
            self.console.stop_generation()
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
            if self._worker_thread.isRunning():
                self._set_status('Please wait for the current response to finish before closing.')
                event.ignore()
                return

        self.console.stop()
        super().closeEvent(event)

    def _init_console(self) -> None:
        try:
            self.console.start()
            self._set_status('Idle')
        except Exception as exc:
            QMessageBox.critical(self, 'Startup Error', str(exc))
            self._set_status('Startup error')

    def _set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _reload_sessions(self) -> None:
        self.session_list.clear()
        sessions = self.repository.list_sessions()
        for session in sessions:
            item = QListWidgetItem(session['title'])
            item.setData(Qt.UserRole, session['id'])
            self.session_list.addItem(item)

    def on_new_chat(self) -> None:
        self.current_session_id = self.repository.create_session('New Chat')
        self._reload_sessions()
        self._select_session_in_list(self.current_session_id)
        self.chat_view.clear()
        self._append_block('System', 'New chat started.')
        self._set_status('Idle')

    def _select_session_in_list(self, session_id: int) -> None:
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.UserRole) == session_id:
                self.session_list.setCurrentItem(item)
                break

    @Slot()
    def on_send(self) -> None:
        user_text = self.input_edit.toPlainText().strip()
        if not user_text:
            return
        if self.current_session_id is None:
            self.on_new_chat()

        assert self.current_session_id is not None
        max_prompt_tokens = prompt_token_budget(self.console.config.ctx_size)
        limited_user_text = limit_prompt_text(user_text, max_prompt_tokens)
        was_limited = limited_user_text != user_text
        self.input_edit.clear()
        self._append_block('You', limited_user_text)
        if was_limited:
            self._append_block('System', 'Your message was shortened to fit the configured context limit.')
        self.repository.add_message(self.current_session_id, 'user', limited_user_text)
        self._generation_stop_requested = False
        self._set_busy(True, 'Generating response...')
        self._start_worker(limited_user_text)

    @Slot()
    def on_stop_generation(self) -> None:
        if self._worker_thread is None or not self._worker_thread.isRunning():
            return

        self._generation_stop_requested = True
        self.stop_btn.setDisabled(True)
        self._set_status('Stopping response...')
        self.console.stop_generation()

    def _start_worker(self, user_text: str) -> None:
        self._worker_thread = QThread()
        self._worker = ChatWorker(self.console, user_text)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_generation_success)
        self._worker.error.connect(self._on_generation_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._cleanup_worker)
        self._worker_thread.start()

    @Slot(str)
    def _on_generation_success(self, answer: str) -> None:
        if self._generation_stop_requested:
            self._append_block('System', 'Generation stopped.')
            self._generation_stop_requested = False
            self._set_busy(False, 'Idle')
            return

        if self.current_session_id is not None:
            self.repository.add_message(self.current_session_id, 'assistant', answer)
        self._append_block('Gemma', answer)
        self._set_busy(False, 'Idle')
        self._reload_sessions()
        if self.current_session_id is not None:
            self._select_session_in_list(self.current_session_id)

    @Slot(str)
    def _on_generation_error(self, error_text: str) -> None:
        if self._generation_stop_requested:
            self._append_block('System', 'Generation stopped.')
            self._generation_stop_requested = False
            self._set_busy(False, 'Idle')
            return

        self._append_block('System', f'Error: {error_text}')
        self._set_busy(False, 'Error')

    @Slot()
    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
        self._worker = None
        self._worker_thread = None

    def _set_busy(self, busy: bool, status_text: str) -> None:
        self.send_btn.setDisabled(busy)
        self.stop_btn.setDisabled(not busy)
        self.new_chat_btn.setDisabled(busy)
        self.session_list.setDisabled(busy)
        self._set_status(status_text)

    @Slot(QListWidgetItem)
    def _on_session_selected(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.UserRole)
        if session_id is None:
            return
        self.current_session_id = int(session_id)
        self._load_session_messages(self.current_session_id)

    def _load_session_messages(self, session_id: int) -> None:
        self.chat_view.clear()
        messages = self.repository.get_messages(session_id)
        if not messages:
            self._append_block('System', 'New chat started.')
            return
        for message in messages:
            role = message['role']
            if role == 'user':
                label = 'You'
            elif role == 'assistant':
                label = 'Gemma'
            else:
                label = 'System'
            self._append_block(label, message['content'])

    def _clear_view_only(self) -> None:
        self.chat_view.clear()

    def _append_block(self, role: str, text: str) -> None:
        text = normalize_text_for_display(text)
        text = strip_unsupported_chars(text)
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f'[{role}]\n{text}\n\n')
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()

    @Slot()
    def _delete_current_chat(self) -> None:
        current_item = self.session_list.currentItem()
        if current_item is None:
            QMessageBox.information(self, 'Delete Session', 'Please select a session first.')
            return

        session_id = current_item.data(Qt.UserRole)
        if session_id is None:
            return

        reply = QMessageBox.question(
            self,
            'Delete Session',
            'Are you sure you want to delete this session?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.repository.delete_session(int(session_id))

        if self.current_session_id == int(session_id):
            self.current_session_id = None
            self.chat_view.clear()
            self._append_block('System', 'Select a session or click New Chat.')

        self._reload_sessions()
        self._set_status('Session deleted')

class ChatGUI:
    def __init__(self, console: LlamaConsoleSession, repository: ChatRepository, app_config: AppConfig) -> None:
        self.console = console
        self.repository = repository
        self.app_config = app_config


    def run(self) -> None:
        app = QApplication.instance() or QApplication([])
        app.setFont(QFont("Arial"))
        window = MainWindow(self.console, self.repository, self.app_config)
        window.show()
        app.exec()
