"""FastAPI app construction for the BFF API Service (007-bff-api-service).

See specs/007-bff-api-service/contracts/bff-api.md for the full route
contract. Routers are registered here as each user story's routes land;
this module itself never implements a route handler directly.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .routes.comparisons import router as comparisons_router
from .routes.reference import router as reference_router
from .routes.reports import router as reports_router
from .routes.scenarios import router as scenarios_router
from .routes.simulations import router as simulations_router

app = FastAPI(
    title="Retirement Planner BFF",
    description="HTTP/JSON API wrapping the retirement_planner library. See specs/007-bff-api-service/.",
    version="0.1.0",
    root_path="",
)

API_PREFIX = "/api/v1"

app.include_router(scenarios_router, prefix=API_PREFIX)
app.include_router(reference_router, prefix=API_PREFIX)
app.include_router(simulations_router, prefix=API_PREFIX)
app.include_router(comparisons_router, prefix=API_PREFIX)
app.include_router(reports_router, prefix=API_PREFIX)


@app.exception_handler(HTTPException)
async def flatten_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Route handlers raise HTTPException(detail={"error": ..., ...}) --
    this flattens that dict directly into the response body instead of
    FastAPI's default {"detail": {...}} wrapper, matching
    contracts/bff-api.md's documented flat error shape (e.g.
    {"error": "no_such_scenario", "name": ...} at the top level)."""
    content = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content)
