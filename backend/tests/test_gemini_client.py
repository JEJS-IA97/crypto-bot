"""Tests rojos — Spec 007: cliente HTTP de Gemini (RF-3/RF-4).

Clave solo por cabecera (nunca en la URL ni en los mensajes de error),
reintentos ante timeout/5xx sin backoff, 429 ⇒ ``GeminiQuotaExceeded``
sin reintento y ``GeminiReply`` con tokens y ``request_id``.
"""

import unittest
from unittest.mock import patch

import httpx

GEN_OK = {
    "candidates": [
        {
            "content": {"parts": [{"text": '{"decision":"WAIT"}'}]},
            "role": "model",
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 120,
        "candidatesTokenCount": 45,
        "totalTokenCount": 165,
    },
}

URL = "https://example.test/v1beta/models/gemini-2.5-flash:generateContent"


class GeminiClientTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.services.gemini_client import GeminiClient

        self.client = GeminiClient(
            api_key="test-key-123",
            model="gemini-2.5-flash",
            base_url="https://example.test/v1beta",
            timeout_seconds=10,
            max_retries=2,
        )

    def test_constructor_rejects_empty_key_or_model(self) -> None:
        from app.services.gemini_client import GeminiClient

        with self.assertRaises(ValueError):
            GeminiClient(api_key="", model="gemini-2.5-flash")
        with self.assertRaises(ValueError):
            GeminiClient(api_key="test-key", model="")

    @patch("app.services.gemini_client.httpx.request")
    def test_generate_ok_returns_reply_and_sends_key_in_header(
        self, request_mock
    ) -> None:
        from app.services.gemini_client import GeminiReply

        request_mock.return_value = httpx.Response(200, json=GEN_OK)

        reply = self.client.generate("analiza BTCUSDT", request_id="req-1")

        self.assertIsInstance(reply, GeminiReply)
        self.assertEqual(reply.text, '{"decision":"WAIT"}')
        self.assertEqual(reply.input_tokens, 120)
        self.assertEqual(reply.output_tokens, 45)
        self.assertEqual(reply.model, "gemini-2.5-flash")
        self.assertEqual(reply.request_id, "req-1")
        self.assertIsInstance(reply.latency_ms, int)
        self.assertGreaterEqual(reply.latency_ms, 0)

        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], "POST")
        url = args[1]
        self.assertEqual(url, URL)
        self.assertNotIn("test-key-123", url)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key-123")
        self.assertEqual(kwargs["timeout"], 10)
        body = kwargs["json"]
        self.assertEqual(
            body["contents"][0]["parts"][0]["text"], "analiza BTCUSDT"
        )
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertEqual(
            body["generationConfig"]["responseMimeType"],
            "application/json",
        )

    @patch("app.services.gemini_client.httpx.request")
    def test_timeout_is_retried_then_succeeds(self, request_mock) -> None:
        request_mock.side_effect = [
            httpx.ReadTimeout("slow"),
            httpx.Response(200, json=GEN_OK),
        ]

        reply = self.client.generate("p", request_id="req-2")

        self.assertEqual(reply.input_tokens, 120)
        self.assertEqual(request_mock.call_count, 2)

    @patch("app.services.gemini_client.httpx.request")
    def test_server_error_exhausts_retries(self, request_mock) -> None:
        from app.services.gemini_client import GeminiUnavailable

        request_mock.return_value = httpx.Response(503, text="server boom")

        with self.assertRaises(GeminiUnavailable) as ctx:
            self.client.generate("p", request_id="req-3")

        self.assertEqual(request_mock.call_count, 3)
        self.assertNotIn("test-key-123", str(ctx.exception))

    @patch("app.services.gemini_client.httpx.request")
    def test_quota_429_is_not_retried(self, request_mock) -> None:
        from app.services.gemini_client import GeminiQuotaExceeded

        request_mock.return_value = httpx.Response(429, text="rate limit")

        with self.assertRaises(GeminiQuotaExceeded):
            self.client.generate("p", request_id="req-4")

        self.assertEqual(request_mock.call_count, 1)

    @patch("app.services.gemini_client.httpx.request")
    def test_unauthorized_is_not_retried(self, request_mock) -> None:
        from app.services.gemini_client import GeminiUnavailable

        request_mock.return_value = httpx.Response(401, text="bad key")

        with self.assertRaises(GeminiUnavailable) as ctx:
            self.client.generate("p", request_id="req-5")

        self.assertEqual(request_mock.call_count, 1)
        self.assertNotIn("test-key-123", str(ctx.exception))

    @patch("app.services.gemini_client.httpx.request")
    def test_empty_candidates_is_not_retried(self, request_mock) -> None:
        from app.services.gemini_client import GeminiUnavailable

        request_mock.return_value = httpx.Response(200, json={"candidates": []})

        with self.assertRaises(GeminiUnavailable):
            self.client.generate("p", request_id="req-6")

        self.assertEqual(request_mock.call_count, 1)

    @patch("app.services.gemini_client.httpx.request")
    def test_missing_usage_metadata_defaults_to_zero_tokens(
        self, request_mock
    ) -> None:
        payload = {"candidates": GEN_OK["candidates"]}
        request_mock.return_value = httpx.Response(200, json=payload)

        reply = self.client.generate("p", request_id="req-7")

        self.assertEqual(reply.input_tokens, 0)
        self.assertEqual(reply.output_tokens, 0)

    @patch("app.services.gemini_client.httpx.request")
    def test_empty_prompt_is_rejected_before_any_call(self, request_mock) -> None:
        with self.assertRaises(ValueError):
            self.client.generate("   ", request_id="req-8")
        request_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
