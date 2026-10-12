"""Unit tests for cholesky_lower() (rp-aev) -- the shared "is this a valid
correlation matrix" primitive both the real Monte Carlo draw
(simulation/returns.py) and scenario/validation.py's pre-flight check
reuse, so the two can never disagree about what counts as valid.
"""

import pytest

from retirement_planner.scenario import DEFAULT_MARKET_ASSUMPTIONS, cholesky_lower

_IDENTITY_3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _flatten(matrix: list[list[float]]) -> list[float]:
    return [value for row in matrix for value in row]


def _reconstruct(lower: list[list[float]]) -> list[list[float]]:
    n = len(lower)
    return [[sum(lower[i][k] * lower[j][k] for k in range(n)) for j in range(n)] for i in range(n)]


def test_identity_matrix_decomposes_to_itself():
    lower = cholesky_lower(_IDENTITY_3)
    assert _flatten(lower) == pytest.approx(_flatten(_IDENTITY_3))


def test_decomposition_reconstructs_the_original_matrix():
    matrix = [[1.0, 0.5, 0.2], [0.5, 1.0, 0.3], [0.2, 0.3, 1.0]]
    lower = cholesky_lower(matrix)
    assert _flatten(_reconstruct(lower)) == pytest.approx(_flatten(matrix))


def test_decomposition_reconstructs_the_real_default_correlation_matrix():
    matrix = DEFAULT_MARKET_ASSUMPTIONS.correlation_matrix
    lower = cholesky_lower(matrix)
    assert _flatten(_reconstruct(lower)) == pytest.approx(_flatten(matrix), abs=1e-9)


def test_rejects_a_non_positive_semi_definite_matrix():
    # High positive correlation between 0-1 and 0-2, but strongly negative
    # between 1-2 -- not a consistent (PSD) correlation structure for 3
    # variables.
    matrix = [[1.0, 0.9, 0.9], [0.9, 1.0, -0.9], [0.9, -0.9, 1.0]]
    with pytest.raises(ValueError):
        cholesky_lower(matrix)


def test_lower_triangular_shape():
    matrix = [[1.0, 0.5, 0.2], [0.5, 1.0, 0.3], [0.2, 0.3, 1.0]]
    lower = cholesky_lower(matrix)
    for i in range(3):
        for j in range(i + 1, 3):
            assert lower[i][j] == 0.0
