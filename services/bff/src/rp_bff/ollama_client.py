"""rp-4p3: the Walkthrough AI Q&A feature's only caller of a local Ollama
daemon. One blocking POST /api/chat per question -- no streaming (plan's
decision #9), "think": false always set (load-bearing: qwen3's default
reasoning-trace mode wraps the answer in a <think> block and roughly
10x's latency, confirmed by direct testing against this environment's
own Ollama install).

`_transport` is a module-level test seam only (httpx.MockTransport, set
by tests/unit/test_ollama_client.py) -- mirrors apps/streamlit_ui's own
api_client.py _transport seam exactly, just on the BFF side this time
since the BFF is the one making the outbound call here.
"""

from __future__ import annotations

import httpx

from .settings import ollama_base_url, ollama_model

_transport: httpx.BaseTransport | None = None

_TIMEOUT_SECONDS = 120.0
"""Independent of apps/streamlit_ui's own blanket 60s api_client.py
default -- confirmed-working warm latency was ~5.6s, but a cold model
load adds a few seconds and a longer question/context will cost more; a
dedicated, more generous timeout here is cheap insurance."""


class OllamaUnavailableError(Exception):
    """The local Ollama daemon isn't reachable, or returned a non-2xx
    response -- mirrors api_client.py's own BackendUnreachableError, on
    the outbound side this time."""

    def __init__(self, *, underlying: Exception | str) -> None:
        self.underlying = underlying
        super().__init__(f"Local Ollama server unavailable: {underlying}")


def ask(system_prompt: str, user_prompt: str) -> str:
    """One blocking, non-streaming /api/chat call, returning the
    assistant message's own content string."""
    try:
        with httpx.Client(base_url=ollama_base_url(), transport=_transport, timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": ollama_model(),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "think": False,
                },
            )
    except httpx.TransportError as exc:
        raise OllamaUnavailableError(underlying=exc) from exc

    if response.status_code != 200:
        raise OllamaUnavailableError(underlying=f"HTTP {response.status_code}: {response.text}")

    return response.json()["message"]["content"]
