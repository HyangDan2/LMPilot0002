from __future__ import annotations

import http.client
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import pexpect

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
TIMING_LINE_RE = re.compile(r"^\[\s*Prompt:.*?\]\s*$", re.MULTILINE)
PROMPT_RE = re.compile(r"(?m)^\s*>\s*$")

BANNER_SKIP_PATTERNS = [
    re.compile(r"^available commands:\s*$", re.IGNORECASE),
    re.compile(r"^\s*/exit.*$", re.IGNORECASE),
    re.compile(r"^\s*/regen.*$", re.IGNORECASE),
    re.compile(r"^\s*/clear.*$", re.IGNORECASE),
    re.compile(r"^\s*/read.*$", re.IGNORECASE),
    re.compile(r"^\s*/glob.*$", re.IGNORECASE),
    re.compile(r"^Loading model\.\.\.\s*$", re.IGNORECASE),
    re.compile(r"^build\s*:.*$", re.IGNORECASE),
    re.compile(r"^model\s*:.*$", re.IGNORECASE),
    re.compile(r"^modalities\s*:.*$", re.IGNORECASE),
    re.compile(r"^using custom system prompt\s*$", re.IGNORECASE),
    re.compile(r"^add a text file\s*$", re.IGNORECASE),
    re.compile(r"^add text files using globbing pattern\s*$", re.IGNORECASE),
]


class ConsoleSessionError(Exception):
    pass


@dataclass
class ConsoleConfig:
    llama_cli_path: str
    model_path: str
    backend: str = "server"
    server_url: str = "http://127.0.0.1:8080"
    server_endpoint: str = "/completion"
    n_predict: int = 512
    system_prompt: Optional[str] = None
    threads: int = 4
    ctx_size: int = 2048
    extra_args: Optional[list[str]] = None
    startup_timeout: float = 180.0
    response_timeout: float = 180.0


class LlamaServerSession:
    def __init__(self, config: ConsoleConfig) -> None:
        self.config = config
        self._active_connection: http.client.HTTPConnection | http.client.HTTPSConnection | None = None
        self._lock = threading.Lock()
        self._started = False
        self._stop_requested = False

    def start(self) -> None:
        self._validate_server_url()
        self._started = True

    def is_alive(self) -> bool:
        return self._started

    def ask(self, user_text: str) -> str:
        if not user_text.strip():
            raise ConsoleSessionError("Empty prompt is not allowed.")

        if not self.is_alive():
            self.start()

        payload = {
            "prompt": user_text,
            "n_predict": self.config.n_predict,
            "stream": False,
        }
        if self.config.extra_args:
            payload.update(self._extra_args_as_payload())

        body = json.dumps(payload).encode("utf-8")
        conn = self._create_connection()

        with self._lock:
            self._stop_requested = False
            self._active_connection = conn

        try:
            conn.request(
                "POST",
                self.config.server_endpoint,
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            response_body = response.read().decode("utf-8", errors="replace")
            if response.status >= 400:
                raise ConsoleSessionError(
                    f"llama-server returned HTTP {response.status}: {response_body}"
                )
            answer = self._extract_server_answer(response_body)
        except (OSError, http.client.HTTPException) as exc:
            if self._stop_requested:
                raise ConsoleSessionError("Generation stopped.") from exc
            raise ConsoleSessionError(f"llama-server request failed: {exc}") from exc
        finally:
            with self._lock:
                if self._active_connection is conn:
                    self._active_connection = None
            conn.close()

        if not answer.strip():
            raise ConsoleSessionError("Model returned an empty response.")
        return answer

    def stop(self, force: bool = False) -> None:
        self.stop_generation()
        self._started = False

    def stop_generation(self) -> None:
        with self._lock:
            self._stop_requested = True
            conn = self._active_connection
        if conn is not None:
            conn.close()

    def _validate_server_url(self) -> None:
        parsed = urlparse(self.config.server_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ConsoleSessionError(f"Invalid llama-server URL: {self.config.server_url}")

    def _create_connection(self) -> http.client.HTTPConnection | http.client.HTTPSConnection:
        parsed = urlparse(self.config.server_url)
        port = parsed.port
        timeout = self.config.response_timeout
        if parsed.scheme == "https":
            return http.client.HTTPSConnection(parsed.hostname, port=port, timeout=timeout)
        return http.client.HTTPConnection(parsed.hostname, port=port, timeout=timeout)

    def _extra_args_as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for item in self.config.extra_args or []:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            payload[key.strip()] = self._parse_payload_value(value.strip())
        return payload

    @staticmethod
    def _parse_payload_value(value: str) -> object:
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    @staticmethod
    def _extract_server_answer(response_body: str) -> str:
        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise ConsoleSessionError(f"Invalid llama-server JSON response: {response_body}") from exc

        if isinstance(data, dict):
            if isinstance(data.get("content"), str):
                return data["content"].strip()
            if isinstance(data.get("completion"), str):
                return data["completion"].strip()
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                choice = choices[0]
                if isinstance(choice, dict):
                    text = choice.get("text")
                    if isinstance(text, str):
                        return text.strip()
                    message = choice.get("message")
                    if isinstance(message, dict) and isinstance(message.get("content"), str):
                        return message["content"].strip()

        raise ConsoleSessionError(f"Unsupported llama-server response: {response_body}")


class LlamaConsoleSession:
    def __init__(self, config: ConsoleConfig) -> None:
        self.config = config
        self.child: Optional[pexpect.spawn] = None
        self._started = False

    def start(self) -> None:
        if self._started and self.is_alive():
            return

        self._validate_paths()
        cmd = self._build_command()
        env = self._build_env()

        self.child = pexpect.spawn(
            command=cmd[0],
            args=cmd[1:],
            env=env,
            encoding="utf-8",
            codec_errors="replace",
            timeout=self.config.startup_timeout,
        )

        try:
            self._wait_for_prompt(self.config.startup_timeout)
            self._started = True
        except Exception as exc:
            startup_dump = self._safe_before()
            self.stop(force=True)
            raise ConsoleSessionError(
                "Failed to start llama-cli.\n"
                f"Command: {' '.join(cmd)}\n\n"
                f"Output:\n{startup_dump}"
            ) from exc

    def is_alive(self) -> bool:
        return self.child is not None and self.child.isalive()

    def ask(self, user_text: str) -> str:
        if not user_text.strip():
            raise ConsoleSessionError("Empty prompt is not allowed.")

        if not self.is_alive():
            self.start()

        assert self.child is not None
        self.child.sendline(user_text)

        raw_block = self._wait_for_prompt(self.config.response_timeout)
        answer = self._extract_answer(raw_block, user_text)

        if not answer.strip():
            raise ConsoleSessionError(
                "Model returned an empty response.\n"
                f"Raw output:\n{self._sanitize_text(raw_block)}"
            )

        return answer

    def stop(self, force: bool = False) -> None:
        if self.child is None:
            self._started = False
            return

        try:
            if self.child.isalive():
                if force:
                    self.child.terminate(force=True)
                else:
                    self.child.sendline("/exit")
                    try:
                        self.child.expect(pexpect.EOF, timeout=5)
                    except pexpect.TIMEOUT:
                        self.child.terminate(force=True)
        finally:
            self.child = None
            self._started = False

    def stop_generation(self) -> None:
        """Interrupt the current response and reset the console for the next prompt."""
        self.stop(force=True)

    def _validate_paths(self) -> None:
        if not os.path.isfile(self.config.llama_cli_path):
            raise ConsoleSessionError(f"llama-cli not found: {self.config.llama_cli_path}")
        if not os.path.isfile(self.config.model_path):
            raise ConsoleSessionError(f"model not found: {self.config.model_path}")

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        llama_bin_dir = os.path.dirname(self.config.llama_cli_path)
        current_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{llama_bin_dir}:{current_ld}" if current_ld else llama_bin_dir
        env.setdefault("TERM", "xterm")
        env.setdefault("COLORTERM", "false")
        env.setdefault("CLICOLOR", "0")
        env.setdefault("NO_COLOR", "1")
        return env

    def _build_command(self) -> list[str]:
        cmd = [
            self.config.llama_cli_path,
            "-m",
            self.config.model_path,
            "--simple-io",
            "--threads",
            str(self.config.threads),
            "--ctx-size",
            str(self.config.ctx_size),
        ]

        if self.config.system_prompt:
            cmd.extend(["--system-prompt", self.config.system_prompt])
        if self.config.extra_args:
            cmd.extend(self.config.extra_args)
        return cmd

    def _wait_for_prompt(self, timeout: float) -> str:
        if self.child is None:
            raise ConsoleSessionError("Console session is not initialized.")

        collected: list[str] = []
        deadline = time.time() + timeout

        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            try:
                idx = self.child.expect([PROMPT_RE, pexpect.EOF, pexpect.TIMEOUT], timeout=remaining)
                if idx == 0:
                    collected.append(self.child.before or "")
                    return "".join(collected)
                if idx == 1:
                    collected.append(self.child.before or "")
                    raise ConsoleSessionError(
                        "llama-cli terminated unexpectedly.\n"
                        f"Output:\n{self._sanitize_text(''.join(collected))}"
                    )
                if idx == 2:
                    continue
            except pexpect.TIMEOUT:
                continue

        raise ConsoleSessionError(
            "Timed out waiting for model response.\n"
            f"Partial output:\n{self._sanitize_text(''.join(collected))}"
        )

    def _extract_answer(self, raw_text: str, user_text: str) -> str:
        text = self._sanitize_text(raw_text)
        lines = text.splitlines()
        cleaned_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append("")
                continue
            if stripped == user_text.strip():
                continue
            if TIMING_LINE_RE.match(stripped):
                continue
            if self._should_skip_line(stripped):
                continue
            cleaned_lines.append(line)

        normalized = "\n".join(cleaned_lines)
        return self._collapse_blank_lines(normalized).strip()

    def _sanitize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = ANSI_ESCAPE_RE.sub("", text)
        text = text.replace("\x00", "")
        return text

    def _should_skip_line(self, line: str) -> bool:
        if line == ">":
            return True
        if re.fullmatch(r"[▄█▀ ]+", line):
            return True
        return any(pattern.match(line) for pattern in BANNER_SKIP_PATTERNS)

    @staticmethod
    def _collapse_blank_lines(text: str) -> str:
        lines = text.split("\n")
        out: list[str] = []
        blank_count = 0
        for line in lines:
            if line.strip() == "":
                blank_count += 1
                if blank_count <= 1:
                    out.append("")
            else:
                blank_count = 0
                out.append(line.rstrip())
        return "\n".join(out).strip()

    def _safe_before(self) -> str:
        if self.child is None:
            return ""
        try:
            return self._sanitize_text(self.child.before or "")
        except Exception:
            return ""
