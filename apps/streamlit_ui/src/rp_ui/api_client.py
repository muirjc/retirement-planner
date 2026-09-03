"""One function per 007 endpoint (research.md §2, data-model.md § API
Client). Each is a thin httpx call against RP_BFF_BASE_URL + <path>,
returning the parsed JSON body (or CSV text for the two export
functions) or raising a typed exception from errors.py. No page script
talks to httpx directly -- this module is the only place that does.

`_transport` is a module-level test seam only (httpx.MockTransport, set
by tests/unit/test_api_client.py) -- production code never sets it, so
`_client()` builds a real httpx.Client against RP_BFF_BASE_URL.
"""

from __future__ import annotations

import os
from typing import cast

import httpx

from .errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    InvalidScenarioError,
    InvalidSimulationOptionsError,
    PathIndexOutOfRangeError,
    ScenarioNotFoundError,
    SurvivalCurveAgeOutOfRangeError,
    UnexpectedBackendError,
    UnknownReferenceValueError,
    UnsupportedTaxYearError,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"

_transport: httpx.BaseTransport | None = None


def _base_url() -> str:
    """Read RP_BFF_BASE_URL fresh on every call (research.md §2) -- never
    cached at import time, so a test or a redeployed backend can change it
    without reloading this module."""
    return os.environ.get("RP_BFF_BASE_URL", DEFAULT_BASE_URL)


def _client() -> httpx.Client:
    return httpx.Client(base_url=_base_url(), transport=_transport, timeout=60.0)


def _request(method: str, path: str, *, json: object = None, params: dict | None = None) -> httpx.Response:
    try:
        with _client() as client:
            return client.request(method, path, json=json, params=params)
    except httpx.TransportError as exc:
        raise BackendUnreachableError(underlying=exc) from exc


def _raise_for_error_response(resp: httpx.Response) -> None:
    """Maps one of 007's documented error shapes (contracts/bff-api.md)
    to its typed exception, by branching on the response's own stable
    `error` field (contracts/bff-api.md's "Consumption expectations" note)
    -- never by string-matching a free-text message. Anything else
    non-2xx becomes UnexpectedBackendError."""
    try:
        body = resp.json()
    except ValueError:
        body = None

    error = body.get("error") if isinstance(body, dict) else None

    if error == "no_such_scenario":
        raise ScenarioNotFoundError(name=body.get("name", ""))
    if error == "invalid_scenario":
        raise InvalidScenarioError(reason=body.get("reason", ""))
    if error == "blocking_validation_flags":
        raise BlockingValidationError(flags=body.get("flags", []))
    if error == "unknown_reference_value":
        raise UnknownReferenceValueError(field=body.get("field", ""), value=body.get("value", ""))
    if error == "estimated_cost_exceeds_budget":
        raise CostBudgetExceededError(
            estimated_seconds=body.get("estimated_seconds", 0.0),
            budget_seconds=body.get("budget_seconds", 0.0),
        )
    if error == "unsupported_tax_year":
        raise UnsupportedTaxYearError(
            figure_name=body.get("figure_name", ""),
            requested_year=body.get("requested_year", 0),
            documented_years=body.get("documented_years", []),
        )
    if error == "path_index_out_of_range":
        raise PathIndexOutOfRangeError(
            requested=body.get("requested", 0),
            path_count=body.get("path_count", 0),
        )
    if error == "survival_curve_age_out_of_range":
        raise SurvivalCurveAgeOutOfRangeError(
            person_name=body.get("person_name", ""),
            age=body.get("age", 0),
        )
    if error == "invalid_simulation_options":
        raise InvalidSimulationOptionsError(detail=body.get("detail", ""))
    raise UnexpectedBackendError(status_code=resp.status_code, body=resp.text)


# rp-cgj: every _json() call site below casts its result to the shape
# 007's own documented contract (contracts/bff-api.md) guarantees for that
# specific endpoint -- _json() itself stays typed `object` (an honest
# description of "whatever httpx.Response.json() actually returned"; this
# module does no client-side schema validation, per its own docstring
# above), so a cast is the accurate way to say "trust the contract here"
# rather than a type: ignore that would silence a real mismatch too.
def _json(method: str, path: str, *, json: object = None, params: dict | None = None) -> object:
    resp = _request(method, path, json=json, params=params)
    if resp.status_code >= 300:
        _raise_for_error_response(resp)
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def _text(method: str, path: str, *, json: object = None, params: dict | None = None) -> str:
    resp = _request(method, path, json=json, params=params)
    if resp.status_code >= 300:
        _raise_for_error_response(resp)
    return resp.text


# -- Scenarios --------------------------------------------------------------


def list_scenarios() -> list[str]:
    """GET /scenarios -- data-model.md § API Client."""
    return cast(dict, _json("GET", "/scenarios"))["scenarios"]


def get_scenario(name: str) -> dict:
    """GET /scenarios/{name} -- raises ScenarioNotFoundError on a 404."""
    return cast(dict, _json("GET", f"/scenarios/{name}"))


def put_scenario(name: str, body: dict) -> dict:
    """PUT /scenarios/{name} -- upsert; the response always includes
    validation_flags/is_usable, even for a scenario with blocking flags
    (contracts/ui-pages.md § 1_Scenarios.py, Acceptance Scenario US1.2)."""
    return cast(dict, _json("PUT", f"/scenarios/{name}", json=body))


def delete_scenario(name: str) -> None:
    """DELETE /scenarios/{name} -- raises ScenarioNotFoundError on a 404."""
    _json("DELETE", f"/scenarios/{name}")
    return None


def validate_scenario(name: str, body: dict) -> dict:
    """POST /scenarios/{name}/validate -- validates without saving."""
    return cast(dict, _json("POST", f"/scenarios/{name}/validate", json=body))


# -- Reference data -----------------------------------------------------------


def list_states() -> list[str]:
    """GET /reference/states -- live from 002's STATE_MODULES (Principle IV)."""
    return cast(dict, _json("GET", "/reference/states"))["states"]


def list_withdrawal_strategies() -> list[str]:
    """GET /reference/withdrawal-strategies -- live from 003's registry."""
    return cast(dict, _json("GET", "/reference/withdrawal-strategies"))["withdrawal_strategies"]


def list_conversion_strategies() -> list[str]:
    """GET /reference/conversion-strategies -- live from 003's registry."""
    return cast(dict, _json("GET", "/reference/conversion-strategies"))["conversion_strategies"]


def list_comparison_axes() -> list[str]:
    """GET /reference/comparison-axes -- 005's full axis set, including
    "state"; 3_Compare.py filters "state" out client-side for the
    Deterministic engine (FR-010)."""
    return cast(dict, _json("GET", "/reference/comparison-axes"))["axes"]


# -- Simulations and comparisons ---------------------------------------------


def run_simulation(body: dict) -> dict:
    """POST /simulations -- {"run": ..., "summary": ..., "account_detail": ...}
    on success (account_detail added by 015-per-account-projection-detail)."""
    return cast(dict, _json("POST", "/simulations", json=body))


def compare_deterministic(body: dict) -> dict:
    """POST /comparisons/deterministic -- {"axis": ..., "summaries": [...],
    "account_detail": [...]} (account_detail added by
    015-per-account-projection-detail, one list per candidate)."""
    return cast(dict, _json("POST", "/comparisons/deterministic", json=body))


def compare_simulated(body: dict) -> dict:
    """POST /comparisons/simulated -- same response shape as
    compare_deterministic(), the only endpoint that accepts axis="state"."""
    return cast(dict, _json("POST", "/comparisons/simulated", json=body))


# -- Reports (CSV export) ------------------------------------------------------


def export_simulation_csv(body: dict) -> str:
    """POST /reports/simulations.csv -- same request body as
    run_simulation(), rendered as CSV text instead of JSON."""
    return _text("POST", "/reports/simulations.csv", json=body)


def export_comparison_csv(body: dict, engine: str) -> str:
    """POST /reports/comparisons.csv?engine=... -- same request body as
    compare_deterministic()/compare_simulated(), rendered as CSV text."""
    return _text("POST", "/reports/comparisons.csv", json=body, params={"engine": engine})
