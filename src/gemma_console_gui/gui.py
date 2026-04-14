from __future__ import annotations

import re
import traceback
from typing import Iterator, Protocol

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QFont, QTextCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

from .config import AppConfig, save_connection_settings
from .console_session import ConsoleConfig, ConsoleSessionError
from .database import ChatRepository
from .llm_client import ChatStreamChunk, OpenAIConnectionSettings
from .session_title import DEFAULT_SESSION_TITLE, derive_session_title
from .token_handler import (
    ModelPrompt,
    build_memory_context,
    build_model_prompt_request,
    normalize_prompt_text,
    prompt_token_budget,
)

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


class ChatSession(Protocol):
    config: ConsoleConfig

    def start(self) -> None: ...
    def stop(self, force: bool = False) -> None: ...
    def stop_generation(self) -> None: ...
    def ask(self, prompt_text: str | ModelPrompt) -> str: ...
    def ask_stream(self, prompt_text: str | ModelPrompt) -> Iterator[ChatStreamChunk]: ...
    def update_connection_settings(self, settings: OpenAIConnectionSettings) -> None: ...
    def test_connection(self) -> str: ...
    def list_models(self) -> list[str]: ...


class ChatWorker(QObject):
    chunk = Signal(str, str)
    finished = Signal(str, bool)
    error = Signal(str)

    def __init__(self, console: ChatSession, prompt_text: str | ModelPrompt) -> None:
        super().__init__()
        self.console = console
        self.prompt_text = prompt_text

    @Slot()
    def run(self) -> None:
        try:
            stream_answer = getattr(self.console, 'ask_stream', None)
            if callable(stream_answer):
                answer_parts: list[str] = []
                for chunk in stream_answer(self.prompt_text):
                    if chunk.kind == 'final':
                        answer_parts.append(chunk.text)
                    self.chunk.emit(chunk.kind, chunk.text)
                self.finished.emit(''.join(answer_parts), True)
                return

            answer = self.console.ask(self.prompt_text)
            self.finished.emit(answer, False)
        except ConsoleSessionError as exc:
            self.error.emit(str(exc))
        except Exception:
            traceback.print_exc()
            self.error.emit('Unexpected internal error while generating a response.')


class ConnectionTestWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, console: ChatSession) -> None:
        super().__init__()
        self.console = console

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.console.test_connection())
        except ConsoleSessionError as exc:
            self.error.emit(str(exc))
        except Exception:
            traceback.print_exc()
            self.error.emit('Unexpected internal error while testing the connection.')


class MainWindow(QMainWindow):
    def __init__(self, console: ChatSession, repository: ChatRepository, app_config: AppConfig) -> None:
        super().__init__()
        self.console = console
        self.repository = repository
        self.app_config = app_config
        self.current_session_id: int | None = None
        self._worker_thread: QThread | None = None
        self._worker: ChatWorker | None = None
        self._connection_test_thread: QThread | None = None
        self._connection_test_worker: ConnectionTestWorker | None = None
        self._generation_stop_requested = False
        self._streaming_assistant_started = False
        self._reasoning_placeholder_start: int | None = None
        self._pending_title_text: str | None = None

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

        settings_group = QGroupBox('OpenAI-Compatible Settings')
        settings_layout = QFormLayout(settings_group)
        self.base_url_edit = QLineEdit(app_config.openai_base_url)
        self.base_url_edit.setPlaceholderText('http://127.0.0.1:8000/v1')
        self.api_key_edit = QLineEdit(app_config.openai_api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText('Optional for local servers')
        self.model_edit = QLineEdit(app_config.openai_model)
        self.model_edit.setPlaceholderText('Model name from your backend')
        self.embedding_model_edit = QLineEdit(app_config.openai_embedding_model)
        self.embedding_model_edit.setPlaceholderText('Optional embedding model for RAG')
        self.save_settings_btn = QPushButton('Save Settings')
        self.save_settings_btn.clicked.connect(self.on_save_connection_settings)
        self.test_connection_btn = QPushButton('Test Connection')
        self.test_connection_btn.clicked.connect(self.on_test_connection)
        settings_button_row = QHBoxLayout()
        settings_button_row.addStretch(1)
        settings_button_row.addWidget(self.save_settings_btn)
        settings_button_row.addWidget(self.test_connection_btn)
        settings_layout.addRow('Base URL', self.base_url_edit)
        settings_layout.addRow('API Key', self.api_key_edit)
        settings_layout.addRow('Model Name', self.model_edit)
        settings_layout.addRow('Embedding Model', self.embedding_model_edit)
        settings_layout.addRow(settings_button_row)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel('Sessions'))
        left_layout.addWidget(self.session_list)
        left_layout.addWidget(self.new_chat_btn)
        left_layout.addWidget(self.delete_chat_btn)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(settings_group)
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

        if self._connection_test_thread is not None and self._connection_test_thread.isRunning():
            self.console.stop_generation()
            self._connection_test_thread.quit()
            self._connection_test_thread.wait(3000)
            if self._connection_test_thread.isRunning():
                self._set_status('Please wait for the connection test to finish before closing.')
                event.ignore()
                return

        self.console.stop()
        super().closeEvent(event)

    def _init_console(self) -> None:
        try:
            self.console.start()
            self._set_status('Idle')
        except ConsoleSessionError as exc:
            QMessageBox.critical(self, 'Startup Error', str(exc))
            self._set_status('Startup error')
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, 'Startup Error', f'Unexpected startup error: {exc}')
            self._set_status('Startup error')

    def _set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _current_connection_settings(self) -> OpenAIConnectionSettings:
        return OpenAIConnectionSettings(
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            model=self.model_edit.text().strip(),
            embedding_model=self.embedding_model_edit.text().strip(),
            temperature=self.app_config.temperature,
            max_tokens=self.app_config.n_predict,
            timeout=self.app_config.response_timeout,
        )

    def _apply_connection_settings(self) -> OpenAIConnectionSettings:
        settings = self._current_connection_settings()
        self.app_config.openai_base_url = settings.base_url
        self.app_config.openai_api_key = settings.api_key
        self.app_config.openai_model = settings.model
        self.app_config.openai_embedding_model = settings.embedding_model
        self.app_config.temperature = settings.temperature
        self.app_config.n_predict = settings.max_tokens
        if hasattr(self.console, 'update_connection_settings'):
            self.console.update_connection_settings(settings)
        return settings

    @Slot()
    def on_save_connection_settings(self) -> None:
        settings = self._apply_connection_settings()
        try:
            save_connection_settings(self.app_config.connection_settings_path, settings)
        except OSError as exc:
            QMessageBox.critical(self, 'Save Settings', f'Could not save settings: {exc}')
            self._set_status('Settings save failed')
            return
        self._set_status('Settings saved')
        self._append_block('System', 'Connection settings saved.')

    @Slot()
    def on_test_connection(self) -> None:
        if self._worker_thread is not None and self._worker_thread.isRunning():
            QMessageBox.information(self, 'Test Connection', 'Please wait for the current response to finish first.')
            return
        if self._connection_test_thread is not None and self._connection_test_thread.isRunning():
            return
        self._apply_connection_settings()
        self.test_connection_btn.setDisabled(True)
        self.save_settings_btn.setDisabled(True)
        self._set_status('Testing connection...')

        self._connection_test_thread = QThread()
        self._connection_test_worker = ConnectionTestWorker(self.console)
        self._connection_test_worker.moveToThread(self._connection_test_thread)
        self._connection_test_thread.started.connect(self._connection_test_worker.run)
        self._connection_test_worker.finished.connect(self._on_connection_test_success)
        self._connection_test_worker.error.connect(self._on_connection_test_error)
        self._connection_test_worker.finished.connect(self._connection_test_thread.quit)
        self._connection_test_worker.error.connect(self._connection_test_thread.quit)
        self._connection_test_thread.finished.connect(self._cleanup_connection_test_worker)
        self._connection_test_thread.start()

    @Slot(str)
    def _on_connection_test_success(self, message: str) -> None:
        self._set_status('Connection OK')
        self._append_block('System', message)

    @Slot(str)
    def _on_connection_test_error(self, error_text: str) -> None:
        self._set_status('Connection failed')
        self._append_block('System', f'Connection test failed: {error_text}')

    @Slot()
    def _cleanup_connection_test_worker(self) -> None:
        if self._connection_test_worker is not None:
            self._connection_test_worker.deleteLater()
        if self._connection_test_thread is not None:
            self._connection_test_thread.deleteLater()
        self._connection_test_worker = None
        self._connection_test_thread = None
        self.test_connection_btn.setDisabled(False)
        self.save_settings_btn.setDisabled(False)

    def _reload_sessions(self) -> None:
        self.session_list.clear()
        sessions = self.repository.list_sessions()
        for session in sessions:
            item = QListWidgetItem(session['title'])
            item.setData(Qt.UserRole, session['id'])
            self.session_list.addItem(item)

    def on_new_chat(self) -> None:
        self.current_session_id = self.repository.create_session(DEFAULT_SESSION_TITLE)
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
        settings = self._apply_connection_settings()
        if self.app_config.backend != "cli" and not settings.base_url:
            QMessageBox.warning(self, 'Missing Base URL', 'Enter a Base URL before sending a prompt.')
            self._set_status('Missing Base URL')
            return
        if self.app_config.backend != "cli" and not settings.model:
            QMessageBox.warning(self, 'Missing Model Name', 'Enter a Model Name before sending a prompt.')
            self._set_status('Missing Model Name')
            return
        if self.current_session_id is None:
            self.on_new_chat()

        assert self.current_session_id is not None
        display_user_text = normalize_prompt_text(user_text)
        if not display_user_text:
            return

        prior_message_count = self.repository.count_messages(self.current_session_id)
        prior_messages = self.repository.get_recent_messages(
            self.current_session_id,
            self.app_config.recent_message_limit,
        )
        memory_context = build_memory_context(
            summary=self.repository.get_session_summary(self.current_session_id),
            max_chars=self.app_config.memory_context_char_limit,
        )
        max_prompt_tokens = prompt_token_budget(
            self.console.config.ctx_size,
            self.app_config.response_token_reserve,
        )
        model_prompt = build_model_prompt_request(
            prior_messages,
            display_user_text,
            max_prompt_tokens,
            self.app_config.max_prompt_chars,
            self.app_config.system_prompt,
            memory_context,
        )
        was_limited = (
            display_user_text != user_text
            or model_prompt.was_limited
            or prior_message_count > len(prior_messages)
        )
        self.input_edit.clear()
        self._append_block('You', display_user_text)
        if was_limited:
            self._append_block('System', 'Prompt context was shortened to fit the configured context limit.')
        self.repository.add_message(self.current_session_id, 'user', display_user_text)
        self._pending_title_text = display_user_text if prior_message_count == 0 else None
        self._generation_stop_requested = False
        self._set_busy(True, 'Generating response...')
        self._start_worker(model_prompt)

    @Slot()
    def on_stop_generation(self) -> None:
        if self._worker_thread is None or not self._worker_thread.isRunning():
            return

        self._generation_stop_requested = True
        self.stop_btn.setDisabled(True)
        self._set_status('Stopping response...')
        self.console.stop_generation()

    def _start_worker(self, prompt_text: str | ModelPrompt) -> None:
        self._streaming_assistant_started = False
        self._worker_thread = QThread()
        self._worker = ChatWorker(self.console, prompt_text)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.chunk.connect(self._on_generation_chunk)
        self._worker.finished.connect(self._on_generation_success)
        self._worker.error.connect(self._on_generation_error)
        self._worker.finished.connect(self._quit_worker_thread_after_success)
        self._worker.error.connect(self._quit_worker_thread_after_error)
        self._worker_thread.finished.connect(self._cleanup_worker)
        self._worker_thread.start()

    @Slot(str, bool)
    def _quit_worker_thread_after_success(self, _answer: str, _was_streamed: bool) -> None:
        if self._worker_thread is not None:
            self._worker_thread.quit()

    @Slot(str)
    def _quit_worker_thread_after_error(self, _error_text: str) -> None:
        if self._worker_thread is not None:
            self._worker_thread.quit()

    @Slot(str, str)
    def _on_generation_chunk(self, kind: str, chunk: str) -> None:
        if kind == 'reasoning':
            self._show_reasoning_placeholder()
            self._set_status('Reasoning...')
            return
        if kind != 'final' or not chunk:
            return
        self._clear_reasoning_placeholder()
        if not self._streaming_assistant_started:
            self._append_block_start('Assistant')
            self._streaming_assistant_started = True
        self._append_stream_text(chunk)
        self._set_status('Generating response...')

    @Slot(str, bool)
    def _on_generation_success(self, answer: str, was_streamed: bool) -> None:
        if self._generation_stop_requested:
            self._clear_reasoning_placeholder()
            self._finish_stream_block()
            self._append_block('System', 'Generation stopped.')
            self._generation_stop_requested = False
            self._pending_title_text = None
            self._set_busy(False, 'Idle')
            return

        self._clear_reasoning_placeholder()
        if not answer.strip():
            self._append_block('System', 'Backend returned no final assistant answer.')
            self._pending_title_text = None
            self._set_busy(False, 'Error')
            return

        if self.current_session_id is not None:
            self.repository.add_message(self.current_session_id, 'assistant', answer)
            self._maybe_update_session_title(self.current_session_id, answer)
        if was_streamed or self._streaming_assistant_started:
            self._finish_stream_block()
        else:
            self._append_block('Assistant', answer)
        self._set_busy(False, 'Idle')
        self._reload_sessions()
        if self.current_session_id is not None:
            self._select_session_in_list(self.current_session_id)

    @Slot(str)
    def _on_generation_error(self, error_text: str) -> None:
        if self._generation_stop_requested:
            self._clear_reasoning_placeholder()
            self._finish_stream_block()
            self._append_block('System', 'Generation stopped.')
            self._generation_stop_requested = False
            self._pending_title_text = None
            self._set_busy(False, 'Idle')
            return

        self._clear_reasoning_placeholder()
        self._finish_stream_block()
        self._append_block('System', f'Error: {error_text}')
        self._pending_title_text = None
        self._set_busy(False, 'Error')

    @Slot()
    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
        self._worker = None
        self._worker_thread = None
        self._streaming_assistant_started = False
        self._reasoning_placeholder_start = None

    def _maybe_update_session_title(self, session_id: int, answer: str) -> None:
        if self._pending_title_text is None:
            return
        current_title = self.repository.get_session_title(session_id)
        if current_title != DEFAULT_SESSION_TITLE:
            self._pending_title_text = None
            return
        title_source = self._pending_title_text or answer
        self.repository.update_session_title(session_id, derive_session_title(title_source))
        self._pending_title_text = None

    def _set_busy(self, busy: bool, status_text: str) -> None:
        self.send_btn.setDisabled(busy)
        self.stop_btn.setDisabled(not busy)
        self.new_chat_btn.setDisabled(busy)
        self.session_list.setDisabled(busy)
        self.test_connection_btn.setDisabled(busy)
        self.save_settings_btn.setDisabled(busy)
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
        blocks = [
            self._format_display_block(self._display_label_for_role(message['role']), message['content'])
            for message in messages
        ]
        self.chat_view.setPlainText(''.join(blocks))
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()

    def _clear_view_only(self) -> None:
        self.chat_view.clear()

    def _append_block(self, role: str, text: str) -> None:
        block = self._format_display_block(role, text)
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(block)
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()

    def _append_block_start(self, role: str) -> None:
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f'[{role}]\n')
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()

    def _show_reasoning_placeholder(self) -> None:
        if self._streaming_assistant_started or self._reasoning_placeholder_start is not None:
            return
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._reasoning_placeholder_start = cursor.position()
        cursor.insertText('[Assistant]\nReasoning...\n\n')
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()

    def _clear_reasoning_placeholder(self) -> None:
        if self._reasoning_placeholder_start is None:
            return
        cursor = self.chat_view.textCursor()
        cursor.setPosition(self._reasoning_placeholder_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()
        self._reasoning_placeholder_start = None

    def _append_stream_text(self, text: str) -> None:
        text = normalize_text_for_display(text)
        text = strip_unsupported_chars(text)
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()

    def _finish_stream_block(self) -> None:
        if not self._streaming_assistant_started:
            return
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText('\n\n')
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()
        self._streaming_assistant_started = False

    def _format_display_block(self, role: str, text: str) -> str:
        text = normalize_text_for_display(text)
        text = strip_unsupported_chars(text)
        return f'[{role}]\n{text}\n\n'

    @staticmethod
    def _display_label_for_role(role: str) -> str:
        if role == 'user':
            return 'You'
        if role == 'assistant':
            return 'Assistant'
        return 'System'

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
    def __init__(self, console: ChatSession, repository: ChatRepository, app_config: AppConfig) -> None:
        self.console = console
        self.repository = repository
        self.app_config = app_config


    def run(self) -> None:
        app = QApplication.instance() or QApplication([])
        app.setFont(QFont("Arial"))
        window = MainWindow(self.console, self.repository, self.app_config)
        window.show()
        app.exec()
