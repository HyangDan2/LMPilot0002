import json
import unittest

from src.gemma_console_gui.console_session import ConsoleConfig, LlamaServerSession


class FakeResponse:
    status = 200

    def read(self) -> bytes:
        return json.dumps({"content": "server answer"}).encode("utf-8")


class FakeConnection:
    requests: list[dict] = []

    def __init__(self) -> None:
        self.closed = False

    def request(self, method: str, endpoint: str, body: bytes, headers: dict) -> None:
        self.requests.append(
            {
                "method": method,
                "endpoint": endpoint,
                "body": json.loads(body.decode("utf-8")),
                "headers": headers,
            }
        )

    def getresponse(self) -> FakeResponse:
        return FakeResponse()

    def close(self) -> None:
        self.closed = True


class ServerSessionTests(unittest.TestCase):
    def test_server_session_posts_completion_payload(self) -> None:
        FakeConnection.requests.clear()
        session = LlamaServerSession(
            ConsoleConfig(
                llama_cli_path="/unused",
                model_path="/unused",
                server_url="http://127.0.0.1:8080",
                n_predict=64,
                extra_args=["temperature=0.2", "cache_prompt=true"],
            )
        )
        session._create_connection = FakeConnection  # type: ignore[method-assign]

        answer = session.ask("[You]\nhello\n\n[Gemma]")

        self.assertEqual(answer, "server answer")
        self.assertEqual(FakeConnection.requests[0]["method"], "POST")
        self.assertEqual(FakeConnection.requests[0]["endpoint"], "/completion")
        self.assertEqual(FakeConnection.requests[0]["body"]["prompt"], "[You]\nhello\n\n[Gemma]")
        self.assertEqual(FakeConnection.requests[0]["body"]["n_predict"], 64)
        self.assertEqual(FakeConnection.requests[0]["body"]["temperature"], 0.2)
        self.assertTrue(FakeConnection.requests[0]["body"]["cache_prompt"])


if __name__ == "__main__":
    unittest.main()
