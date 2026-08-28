"""Polish: FastAPI's auto-generated /docs (Swagger UI) and /openapi.json
are reachable and enumerate every route this feature registers --
docs/frontend_architecture.md §2's stated benefit of choosing FastAPI: a
usable manual-testing surface that exists before any real UI is built."""

from fastapi.testclient import TestClient

from rp_bff.main import app

_EXPECTED_PATHS = {
    "/api/v1/scenarios",
    "/api/v1/scenarios/{name}",
    "/api/v1/scenarios/{name}/validate",
    "/api/v1/reference/states",
    "/api/v1/reference/withdrawal-strategies",
    "/api/v1/reference/conversion-strategies",
    "/api/v1/reference/comparison-axes",
    "/api/v1/simulations",
    "/api/v1/comparisons/deterministic",
    "/api/v1/comparisons/simulated",
    "/api/v1/reports/simulations.csv",
    "/api/v1/reports/comparisons.csv",
}


def test_docs_and_openapi_json_are_reachable():
    client = TestClient(app)

    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    registered_paths = set(openapi_response.json()["paths"].keys())
    assert _EXPECTED_PATHS.issubset(registered_paths)
