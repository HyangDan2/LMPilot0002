import json
import unittest

from src.gemma_console_gui.llm_client import LLMClientError, OpenAICompatibleClient, OpenAIConnectionSettings


class FakeResponse:
    def __init__(self, status: int, body: dict) -> None:
        self.status = status
        self.body = body

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


class FakeConnection:
    requests: list[dict] = []
    responses: list[FakeResponse] = []

    def __init__(self) -> None:
        self.closed = False

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None) -> None:
        self.requests.append(
            {
                "method": method,
                "path": path,
                "body": json.loads(body.decode("utf-8")) if body else None,
                "headers": headers or {},
            }
        )

    def getresponse(self) -> FakeResponse:
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class OpenAICompatibleClientTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeConnection.requests.clear()
        FakeConnection.responses.clear()

    def make_client(self, settings: OpenAIConnectionSettings) -> OpenAICompatibleClient:
        client = OpenAICompatibleClient(settings)
        client._create_connection = lambda parsed: FakeConnection()  # type: ignore[method-assign]
        return client

    def test_chat_completion_posts_openai_compatible_payload(self) -> None:
        FakeConnection.responses.append(
            FakeResponse(200, {"choices": [{"message": {"content": "hello"}}]})
        )
        client = self.make_client(
            OpenAIConnectionSettings(
                base_url="http://localhost:1234/v1/",
                api_key="sk-secret",
                model="local-model",
                temperature=0.2,
                max_tokens=64,
            )
        )

        answer = client.chat_completion([{"role": "user", "content": "Hi"}])

        self.assertEqual(answer, "hello")
        request = FakeConnection.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"], "/v1/chat/completions")
        self.assertEqual(request["headers"]["Authorization"], "Bearer sk-secret")
        self.assertEqual(request["body"]["model"], "local-model")
        self.assertEqual(request["body"]["messages"], [{"role": "user", "content": "Hi"}])
        self.assertFalse(request["body"]["stream"])

    def test_list_models_uses_base_url_prefix(self) -> None:
        FakeConnection.responses.append(
            FakeResponse(200, {"data": [{"id": "model-a"}, {"id": "model-b"}]})
        )
        client = self.make_client(OpenAIConnectionSettings(base_url="https://example.test/v1"))

        self.assertEqual(client.list_models(), ["model-a", "model-b"])
        self.assertEqual(FakeConnection.requests[0]["path"], "/v1/models")

    def test_embeddings_posts_openai_compatible_payload(self) -> None:
        FakeConnection.responses.append(
            FakeResponse(
                200,
                {
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                },
            )
        )
        client = self.make_client(
            OpenAIConnectionSettings(
                base_url="http://localhost:1234/v1",
                model="chat-model",
                embedding_model="embedding-model",
            )
        )

        vectors = client.embeddings(["first", "second"])

        self.assertEqual(vectors, [[1.0, 0.0], [0.0, 1.0]])
        request = FakeConnection.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"], "/v1/embeddings")
        self.assertEqual(request["body"]["model"], "embedding-model")
        self.assertEqual(request["body"]["input"], ["first", "second"])

    def test_http_error_is_readable_without_credentials(self) -> None:
        FakeConnection.responses.append(FakeResponse(401, {"error": "bad key"}))
        client = self.make_client(
            OpenAIConnectionSettings(base_url="http://localhost:1234/v1", api_key="sk-secret", model="model")
        )

        with self.assertRaises(LLMClientError) as raised:
            client.chat_completion([{"role": "user", "content": "Hi"}])

        self.assertIn("HTTP 401", str(raised.exception))
        self.assertNotIn("sk-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
