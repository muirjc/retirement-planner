"""Integration tests for POST /api/v1/walkthrough/ask (rp-4p3) -- the
outbound Ollama call is mocked via rp_bff.ollama_client's own
httpx.MockTransport seam, so this never needs a real Ollama daemon.
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


def test_ask_route_returns_answer_on_success(client):
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "Yes, that RMD figure is verified."}})

    _install(handler)
    response = client.post(
        "/api/v1/walkthrough/ask",
        json={
            "question": "Is the RMD figure verified?",
            "plan_years": [{"plan_year": 1, "entries": [], "figure_citations": []}],
        },
    )
    assert response.status_code == 200
    assert response.json() == {"answer": "Yes, that RMD figure is verified."}


def test_ask_route_forwards_question_and_plan_years_into_the_prompt(client):
    captured = {}

    def handler(request):
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    _install(handler)
    client.post(
        "/api/v1/walkthrough/ask",
        json={"question": "why did taxes go up?", "plan_years": [{"plan_year": 2}]},
    )
    user_message = captured["body"]["messages"][1]["content"]
    assert "why did taxes go up?" in user_message
    assert '"plan_year": 2' in user_message


def test_ask_route_maps_connection_failure_to_ollama_unavailable(client):
    def handler(request):
        raise httpx.ConnectError("refused")

    _install(handler)
    response = client.post(
        "/api/v1/walkthrough/ask",
        json={"question": "anything", "plan_years": []},
    )
    assert response.status_code == 503
    assert response.json()["error"] == "ollama_unavailable"


def test_ask_route_maps_non_2xx_ollama_response_to_ollama_unavailable(client):
    def handler(request):
        return httpx.Response(500, text="model not found")

    _install(handler)
    response = client.post(
        "/api/v1/walkthrough/ask",
        json={"question": "anything", "plan_years": []},
    )
    assert response.status_code == 503
    assert response.json()["error"] == "ollama_unavailable"
