"""Unit tests for src/rp_ui/api_client.py -- T005.

Uses httpx.MockTransport fixtures built from 007's actual documented
response shapes (specs/007-bff-api-service/contracts/bff-api.md), not
guessed shapes, per research.md §2's testing decision. Covers: each of
007's 5 documented error responses raises the corresponding rp_ui.errors
type; a connection failure raises BackendUnreachableError; an
unrecognized non-2xx raises UnexpectedBackendError; and a 2xx response
returns its parsed JSON body (or CSV text for the export endpoints).
"""

import httpx
import pytest

from rp_ui import api_client
from rp_ui.errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    InvalidScenarioError,
    ScenarioNotFoundError,
    UnexpectedBackendError,
    UnknownReferenceValueError,
)


@pytest.fixture(autouse=True)
def _reset_transport():
    """Every test installs its own transport; always clear it after so one
    test's mock never leaks into the next (module-level state, per
    research.md §2's "thin module of functions" design)."""
    yield
    api_client._transport = None


def _install(handler) -> None:
    api_client._transport = httpx.MockTransport(handler)


def test_list_scenarios_returns_parsed_list():
    def handler(request):
        assert request.url.path == "/api/v1/scenarios"
        return httpx.Response(200, json={"scenarios": ["base_case", "aggressive"]})

    _install(handler)
    assert api_client.list_scenarios() == ["base_case", "aggressive"]


def test_run_simulation_returns_parsed_body():
    def handler(request):
        assert request.url.path == "/api/v1/simulations"
        return httpx.Response(200, json={"run": {"candidate_label": "base_case"}, "summary": {"success_rate": 0.92}})

    _install(handler)
    result = api_client.run_simulation({"scenario_name": "base_case"})
    assert result["summary"]["success_rate"] == 0.92


def test_export_simulation_csv_returns_text():
    def handler(request):
        assert request.url.path == "/api/v1/reports/simulations.csv"
        return httpx.Response(200, text="plan_year,ending_balance\n1,100000\n")

    _install(handler)
    text = api_client.export_simulation_csv({"scenario_name": "base_case"})
    assert text.startswith("plan_year,ending_balance")


def test_export_comparison_csv_passes_engine_query_param():
    def handler(request):
        assert request.url.path == "/api/v1/reports/comparisons.csv"
        assert request.url.params["engine"] == "simulated"
        return httpx.Response(200, text="candidate_label,ending_balance\n")

    _install(handler)
    api_client.export_comparison_csv({"scenario_name": "base_case"}, engine="simulated")


def test_no_such_scenario_raises_scenario_not_found_error():
    def handler(request):
        return httpx.Response(404, json={"error": "no_such_scenario", "name": "ghost"})

    _install(handler)
    with pytest.raises(ScenarioNotFoundError) as exc_info:
        api_client.get_scenario("ghost")
    assert exc_info.value.name == "ghost"


def test_invalid_scenario_raises_invalid_scenario_error():
    def handler(request):
        return httpx.Response(422, json={"error": "invalid_scenario", "reason": "accounts[0].balance must be >= 0"})

    _install(handler)
    with pytest.raises(InvalidScenarioError) as exc_info:
        api_client.put_scenario("base_case", {})
    assert "must be >= 0" in exc_info.value.reason


def test_blocking_validation_flags_raises_blocking_validation_error():
    flags = [{"field": "accounts[0].balance", "message": "must be >= 0", "severity": "blocking"}]

    def handler(request):
        return httpx.Response(422, json={"error": "blocking_validation_flags", "flags": flags})

    _install(handler)
    with pytest.raises(BlockingValidationError) as exc_info:
        api_client.run_simulation({"scenario_name": "base_case"})
    assert exc_info.value.flags == flags


def test_unknown_reference_value_raises_unknown_reference_value_error():
    def handler(request):
        return httpx.Response(422, json={"error": "unknown_reference_value", "field": "state", "value": "ZZ"})

    _install(handler)
    with pytest.raises(UnknownReferenceValueError) as exc_info:
        api_client.run_simulation({"scenario_name": "base_case", "state": "ZZ"})
    assert exc_info.value.field == "state"
    assert exc_info.value.value == "ZZ"


def test_cost_budget_exceeded_raises_cost_budget_exceeded_error():
    def handler(request):
        return httpx.Response(
            413,
            json={"error": "estimated_cost_exceeds_budget", "estimated_seconds": 180.0, "budget_seconds": 30.0},
        )

    _install(handler)
    with pytest.raises(CostBudgetExceededError) as exc_info:
        api_client.run_simulation({"scenario_name": "base_case"})
    assert exc_info.value.estimated_seconds == 180.0
    assert exc_info.value.budget_seconds == 30.0


def test_connection_failure_raises_backend_unreachable_error():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _install(handler)
    with pytest.raises(BackendUnreachableError):
        api_client.list_scenarios()


def test_unrecognized_error_shape_raises_unexpected_backend_error():
    def handler(request):
        return httpx.Response(500, text="internal server error")

    _install(handler)
    with pytest.raises(UnexpectedBackendError) as exc_info:
        api_client.list_scenarios()
    assert exc_info.value.status_code == 500


def test_delete_scenario_returns_none_on_204():
    def handler(request):
        assert request.method == "DELETE"
        return httpx.Response(204)

    _install(handler)
    assert api_client.delete_scenario("base_case") is None


def test_base_url_defaults_and_respects_env_var(monkeypatch):
    monkeypatch.delenv("RP_BFF_BASE_URL", raising=False)
    assert api_client._base_url() == "http://127.0.0.1:8000/api/v1"
    monkeypatch.setenv("RP_BFF_BASE_URL", "http://example.test/api/v1")
    assert api_client._base_url() == "http://example.test/api/v1"
