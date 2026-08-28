"""POST /reports/simulations.csv and POST /reports/comparisons.csv
(FR-016-FR-017): the same request bodies as /simulations and
/comparisons/*, rendered through 006's CSV export functions instead of its
summarization functions -- reusing routes/simulations.py's and
routes/comparisons.py's own resolve-and-run/resolve-and-compare helpers,
never a separate "export parameters" shape (data-model.md § Export
Response). See specs/007-bff-api-service/contracts/bff-api.md § Reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from retirement_planner.reporting import (
    deterministic_comparison_to_csv_text,
    run_to_csv_text,
    simulation_comparison_to_csv_text,
)

from ..dependencies import get_scenarios_dir
from .comparisons import ComparisonRequest, resolve_and_compare_deterministic, resolve_and_compare_simulated
from .simulations import SimulationRequest, resolve_and_run_simulation

router = APIRouter()


@router.post("/reports/simulations.csv")
def export_simulation_route(
    body: SimulationRequest, scenarios_dir: Path | None = Depends(get_scenarios_dir)
) -> PlainTextResponse:
    """POST /reports/simulations.csv -- same body as POST /simulations,
    rendered via 006's run_to_csv_text() instead of summarize_run()
    (FR-016-FR-017, US5.1, US5.3)."""
    context, run = resolve_and_run_simulation(body, scenarios_dir)
    return PlainTextResponse(content=run_to_csv_text(run), media_type="text/csv")


@router.post("/reports/comparisons.csv")
def export_comparison_route(
    body: ComparisonRequest,
    engine: Literal["deterministic", "simulated"] = Query(...),
    scenarios_dir: Path | None = Depends(get_scenarios_dir),
) -> PlainTextResponse:
    """POST /reports/comparisons.csv -- same body as the corresponding
    POST /comparisons/{engine}, rendered via 006's
    deterministic_comparison_to_csv_text()/simulation_comparison_to_csv_text()
    instead of the summarize_*_comparison() functions (FR-016-FR-017,
    US5.2-US5.3)."""
    if engine == "deterministic":
        context, result = resolve_and_compare_deterministic(body, scenarios_dir)
        csv_text = deterministic_comparison_to_csv_text(result, household=context.household, reference_tax_year=body.reference_tax_year)
    else:
        context, result = resolve_and_compare_simulated(body, scenarios_dir)
        csv_text = simulation_comparison_to_csv_text(result, household=context.household, reference_tax_year=body.reference_tax_year)
    return PlainTextResponse(content=csv_text, media_type="text/csv")
