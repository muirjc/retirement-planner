"""Pure linear-algebra helper for the 8-asset-class correlation matrix
(rp-aev). Lives in `scenario`, not `simulation`, even though its only real
caller for *generating* correlated returns is `simulation/returns.py` --
`scenario/validation.py` also needs it (to reject an invalid correlation
matrix at save/validate time) and `scenario` sits upstream of `simulation`
in this codebase's strict, acyclic package chain (`scenario -> tax ->
mechanics -> comparison -> simulation -> reporting`,
docs/SOLUTION_ARCHITECTURE.md §3) -- `scenario` can never import from
`simulation`, so this function has to live here, the common ancestor both
call sites can reach. `simulation/returns.py` imports it from here.

No numpy/scipy dependency -- this codebase has none, and an 8x8 (or any
small N) Cholesky decomposition is trivial in pure Python.
"""

from __future__ import annotations

import math


def cholesky_lower(matrix: list[list[float]]) -> list[list[float]]:
    """Standard lower-triangular Cholesky decomposition: returns L such
    that L @ L.T == matrix. Raises ValueError the instant a diagonal
    pivot would require sqrt() of a value <= 0 -- this IS the "is this a
    valid (positive-semi-definite) correlation matrix" check, reused by
    both the real Monte Carlo draw (simulation/returns.py) and
    scenario/validation.py's pre-flight check, so the two can never
    disagree about what counts as valid.
    """
    n = len(matrix)
    lower: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            partial_sum = sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                diagonal_value = matrix[i][i] - partial_sum
                if diagonal_value <= 0.0:
                    raise ValueError(f"correlation matrix is not positive-semi-definite at row {i}")
                lower[i][j] = math.sqrt(diagonal_value)
            else:
                lower[i][j] = (matrix[i][j] - partial_sum) / lower[j][j]
    return lower
