"""Historical annual real-return series for generate_historical_bootstrap_paths()
(FR-012, research.md §4).

The source document's own Assumptions suggest a broad-coverage equity/bond
total-return series spanning approximately 1926-present (docs/initial_requirement.md
§10 Open Question: "which return series... and what date range?"). Consistent
with Constitution Principle V (Offline-First, No Runtime Network Dependency),
this feature cannot fetch that series at runtime or at authoring time in this
environment -- so HISTORICAL_RETURNS below is **synthetic placeholder data**,
not actual historical market returns. It is generated deterministically (a
fixed local seed, independent of any caller-supplied seed) purely to give the
moving-block-bootstrap mechanic (research.md §4) a structurally complete,
reproducible table to resample from, matching the illustrative-figure
precedent 002-tax-calculation-engine's state tax modules already set (e.g.
SC's "illustrative placeholders... not asserted as the actual current SC
Code figures"). `verified=False` reflects that honestly, per Principle III --
this table MUST NOT be marked verified until replaced with a real, cited
historical return series and confirmed against a primary source.
"""

from __future__ import annotations

import random
from datetime import date

from retirement_planner.tax import SourcedFigure

_SYNTHETIC_SERIES_SEED = 1926  # fixed, independent of caller seeds -- see module docstring
_FIRST_YEAR = 1926
_LAST_YEAR = 2025


def _build_synthetic_series() -> dict[int, tuple[float, float]]:
    """Builds the module-docstring's synthetic placeholder (equity_return,
    bond_return) schedule, keyed by calendar year, deterministically from
    _SYNTHETIC_SERIES_SEED."""
    rng = random.Random(_SYNTHETIC_SERIES_SEED)
    schedule: dict[int, tuple[float, float]] = {}
    for year in range(_FIRST_YEAR, _LAST_YEAR + 1):
        equity_real_return = rng.gauss(0.065, 0.19)
        bond_real_return = rng.gauss(0.02, 0.08)
        schedule[year] = (equity_real_return, bond_real_return)
    return schedule


HISTORICAL_RETURNS: SourcedFigure[tuple[float, float]] = SourcedFigure(
    name="historical_annual_real_returns",
    schedule=_build_synthetic_series(),
    citation=(
        "SYNTHETIC PLACEHOLDER -- not an actual historical return series. Intended "
        "eventual source: a broad-market equity total-return index (e.g. S&P 500) "
        "and an aggregate bond index, annual real returns, ~1926-present "
        "(docs/initial_requirement.md §10 Open Question; exact series and date range "
        "not yet selected)."
    ),
    last_verified=date(2026, 8, 28),
    verified=False,
)
