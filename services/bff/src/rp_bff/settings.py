"""rp-4p3: the BFF's first settings module -- two env-var-driven values
for the Walkthrough AI Q&A feature's local Ollama call. Read fresh with
os.environ.get(...) on every call (not cached at import time), matching
the one config pattern this codebase already has (apps/streamlit_ui's
own api_client.py _base_url()), rather than introducing a Pydantic
Settings framework for two values.
"""

from __future__ import annotations

import os

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11435"
DEFAULT_OLLAMA_MODEL = "qwen3:latest"


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
