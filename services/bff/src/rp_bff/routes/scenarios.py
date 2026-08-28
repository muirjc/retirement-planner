"""Scenario CRUD + validate routes (FR-001-FR-005): GET/PUT/GET-by-name/
DELETE /scenarios, POST /scenarios/{name}/validate. Every operation calls
001's own save_scenario()/load_scenario()/list_scenarios()/
delete_scenario()/parse_scenario()/validate() unchanged (research.md §3) --
this module performs no scenario computation of its own. See
specs/007-bff-api-service/contracts/bff-api.md § Scenarios.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Response

from retirement_planner.scenario import (
    ScenarioParseError,
    delete_scenario,
    list_scenarios,
    load_scenario,
    parse_scenario,
    save_scenario,
    validate,
)

from ..dependencies import get_scenarios_dir
from ..schemas import ScenarioRequest
from ..serialization import to_jsonable

router = APIRouter()


def _no_such_scenario(name: str) -> HTTPException:
    """The shared 404 shape for a scenario name that doesn't exist (or no
    longer does) -- contracts/bff-api.md's no_such_scenario error, FR-005."""
    return HTTPException(status_code=404, detail={"error": "no_such_scenario", "name": name})


def _scenario_to_response(scenario) -> dict:
    """to_jsonable() only sees dataclass fields, not properties --
    Scenario.is_usable is a computed @property (data-model.md's own
    "including validation_flags and is_usable" promise), so it's merged
    in explicitly rather than generalizing the serializer to guess at
    properties on every dataclass it recurses through (found while
    implementing US1: test_save_read_and_list_round_trip failed with
    KeyError: 'is_usable' against the naive to_jsonable(scenario) call)."""
    return {**to_jsonable(scenario), "is_usable": scenario.is_usable}


def _request_to_yaml_text(body: ScenarioRequest) -> str:
    """Converts a validated ScenarioRequest to YAML text -- the route
    handler then calls 001's own parse_scenario() on that text, rather
    than hand-building a Scenario object field-by-field, keeping exactly
    one parse/construct code path in existence (research.md §3)."""
    return yaml.safe_dump(body.model_dump(mode="json"), sort_keys=False)


@router.get("/scenarios")
def list_scenarios_route(scenarios_dir: Path | None = Depends(get_scenarios_dir)) -> dict:
    """GET /scenarios -- 001's list_scenarios() unchanged (FR-001, US1.2)."""
    return {"scenarios": list_scenarios(scenarios_dir=scenarios_dir)}


@router.get("/scenarios/{name}")
def get_scenario_route(name: str, scenarios_dir: Path | None = Depends(get_scenarios_dir)) -> dict:
    """GET /scenarios/{name} -- 001's load_scenario() unchanged (FR-001, US1.1)."""
    try:
        scenario = load_scenario(name, scenarios_dir=scenarios_dir)
    except ScenarioParseError:
        raise _no_such_scenario(name)
    return _scenario_to_response(scenario)


@router.put("/scenarios/{name}")
def put_scenario_route(
    name: str, body: ScenarioRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)
) -> dict:
    """PUT /scenarios/{name} -- upsert: 001's parse_scenario()+validate()+
    save_scenario() unchanged, always overwriting any existing scenario of
    the same name (FR-001, FR-003, US1.1, US1.4). Saving never requires
    validity (001's own save_scenario() contract) -- a blocking flag is
    reported, not rejected."""
    try:
        scenario = parse_scenario(_request_to_yaml_text(body), name=name)
    except ScenarioParseError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_scenario", "reason": exc.reason})
    scenario.validation_flags = validate(scenario)
    save_scenario(scenario, scenarios_dir=scenarios_dir)
    return _scenario_to_response(scenario)


@router.delete("/scenarios/{name}", status_code=204)
def delete_scenario_route(name: str, scenarios_dir: Path | None = Depends(get_scenarios_dir)) -> Response:
    """DELETE /scenarios/{name} -- the 001 prerequisite delete_scenario()
    unchanged (FR-004, US1.5)."""
    try:
        delete_scenario(name, scenarios_dir=scenarios_dir)
    except ScenarioParseError:
        raise _no_such_scenario(name)
    return Response(status_code=204)


@router.post("/scenarios/{name}/validate")
def validate_scenario_route(name: str, body: ScenarioRequest) -> dict:
    """POST /scenarios/{name}/validate -- 001's parse_scenario()+
    validate() unchanged, with no save side effect (FR-002, US1.3)."""
    try:
        scenario = parse_scenario(_request_to_yaml_text(body), name=name)
    except ScenarioParseError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_scenario", "reason": exc.reason})
    flags = validate(scenario)
    return {
        "validation_flags": to_jsonable(flags),
        "is_usable": all(flag.severity != "blocking" for flag in flags),
    }
