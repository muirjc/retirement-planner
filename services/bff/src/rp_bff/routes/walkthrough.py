"""POST /walkthrough/ask (rp-4p3): answers a free-text question about the
Walkthrough page's own already-computed plan years, via a local Ollama
model. The BFF stays stateless here exactly like every other route --
`plan_years` is the UI's own already-held YearStory-shaped JSON for
whichever batch of years is in view, forwarded verbatim as an opaque
passthrough (not a fully re-typed Pydantic mirror of YearStory/
YearComputationDetail -- that structure is complex, already locked on
the core side, and never field-validated here, only formatted into a
prompt). No new simulation re-run, no run lookup, no persistence. See
plans/rustling-chasing-cat.md (rp-4p3) for the full design rationale.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ollama_client import OllamaUnavailableError, ask

router = APIRouter()

_SYSTEM_PROMPT = """You are an assistant embedded in a retirement planning tool's \
"Walkthrough" page. You are given one or more plan years' worth of already-computed, \
deterministic data as JSON (narrative entries, a full computation breakdown, and \
figure citations) and a user's question about it.

Rules you must follow:
- Only use numbers and facts present in the provided JSON. Never recompute, estimate, \
or invent a number -- quote figures verbatim from the data.
- If asked whether a figure is verified or accurate, answer honestly from that \
figure's own `verified` and `citation` fields in `figure_citations` -- never claim \
confidence the data itself doesn't have.
- Do not give general tax, legal, or financial advice beyond explaining what this \
tool computed and why, as shown in the data.
- If the data doesn't contain what's needed to answer, say so plainly rather than \
guessing.
- Answer in clear, concise prose aimed at the plan's own user, not a developer."""


class WalkthroughAskRequest(BaseModel):
    question: str
    plan_years: list[dict]


def _ollama_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "ollama_unavailable",
            "message": "Local AI model unavailable -- is Ollama running with a model pulled?",
        },
    )


@router.post("/walkthrough/ask")
def ask_walkthrough_route(body: WalkthroughAskRequest) -> dict:
    """POST /walkthrough/ask -- grounds the model strictly in body.plan_years
    (rp-4p3 decisions #2-#3), returning {"answer": str}."""
    user_prompt = (
        f"Plan year data (JSON):\n{json.dumps(body.plan_years, default=str)}\n\n"
        f"Question: {body.question}"
    )
    try:
        answer = ask(_SYSTEM_PROMPT, user_prompt)
    except OllamaUnavailableError:
        raise _ollama_unavailable()
    return {"answer": answer}
