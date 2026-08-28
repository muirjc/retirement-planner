"""Shared pytest fixtures for services/bff's test suite.

Every integration test that exercises the HTTP app MUST use the `client`
fixture (never construct TestClient(app) directly) -- it isolates scenario
storage into a fresh tmp_path per test via app.dependency_overrides,
mirroring the core package's own tests/conftest.py::scenario_store_dir
discipline for the same reason (never touch the real config/scenarios/
directory from a test).
"""

import pytest
from fastapi.testclient import TestClient

from rp_bff.dependencies import get_scenarios_dir
from rp_bff.main import app


@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_scenarios_dir] = lambda: tmp_path
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
