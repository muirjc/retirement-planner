"""Unit tests for rp_bff.ollama_client (rp-4p3).

Uses httpx.MockTransport, mirroring apps/streamlit_ui/tests/unit/
test_api_client.py's own _transport seam pattern -- the first use of
MockTransport inside services/bff/tests/ itself, since this is the
first outbound HTTP call the BFF has ever made.
"""

import httpx
import pytest

from rp_bff import ollama_client


@pytest.fixture(autouse=True)
def _reset_transport():
    yield
    ollama_client._transport = None


def _install(handler) -> None:
    ollama_client._transport = httpx.MockTransport(handler)


def test_ask_sends_non_streaming_non_thinking_request_and_returns_content():
    def handler(request):
        import json

        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ]
        return httpx.Response(200, json={"message": {"content": "the answer"}})

    _install(handler)
    assert ollama_client.ask("sys", "usr") == "the answer"


def test_ask_raises_ollama_unavailable_on_connection_failure():
    def handler(request):
        raise httpx.ConnectError("refused")

    _install(handler)
    with pytest.raises(ollama_client.OllamaUnavailableError):
        ollama_client.ask("sys", "usr")


def test_ask_raises_ollama_unavailable_on_non_2xx():
    def handler(request):
        return httpx.Response(500, text="model not found")

    _install(handler)
    with pytest.raises(ollama_client.OllamaUnavailableError):
        ollama_client.ask("sys", "usr")
