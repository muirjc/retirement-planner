"""Unit test confirming GET /reference/states reads STATE_MODULES live,
not a cached snapshot (Acceptance Scenario US2.2, Principle IV) -- a state
module registered in a future 002 change must appear here with zero
change to this service.
"""

from fastapi.testclient import TestClient

from rp_bff.main import app


def test_reference_states_reflects_a_live_registry_change(monkeypatch):
    from retirement_planner.tax import STATE_MODULES
    from retirement_planner.tax.state.fl import compute_tax as fl_compute_tax

    client = TestClient(app)

    before = client.get("/api/v1/reference/states").json()["states"]
    assert "ZZ" not in before

    # Mutate the same dict object in place (not a reassignment) -- exactly
    # how a future 002 state-module addition would register itself.
    monkeypatch.setitem(STATE_MODULES, "ZZ", fl_compute_tax)

    after = client.get("/api/v1/reference/states").json()["states"]
    assert "ZZ" in after
    assert after == sorted(STATE_MODULES.keys())
