"""Historical annual real-return series for generate_historical_bootstrap_paths()
(rp-aev: widened from 2 to 8 asset classes).

The source document's own Assumptions suggest a broad-coverage equity/bond
total-return series spanning approximately 1926-present (docs/initial_requirement.md
§10 Open Question: "which return series... and what date range?"). Consistent
with Constitution Principle V (Offline-First, No Runtime Network Dependency),
this feature cannot fetch that series at runtime or at authoring time in this
environment -- so HISTORICAL_RETURNS below is **synthetic placeholder data**,
not actual historical market returns. It is generated deterministically (a
fixed local seed, independent of any caller-supplied seed) purely to give the
moving-block-bootstrap mechanic a structurally complete, reproducible table to
resample from, matching the illustrative-figure precedent 002-tax-calculation-engine's
state tax modules already set (e.g. SC's "illustrative placeholders... not
asserted as the actual current SC Code figures"). `verified=False` reflects
that honestly, per Principle III -- this table MUST NOT be marked verified
until replaced with a real, cited historical return series and confirmed
against a primary source.

rp-aev: widened from a 2-column (equity, bond) series to an 8-column one
(one per AssetClass), using DEFAULT_MARKET_ASSUMPTIONS's own mean/std AND
correlation_matrix (via cholesky_lower()) -- fixing a pre-existing
inconsistency where the old 2-asset synthetic series drew equity/bond
independently, uncorrelated, unlike the live parametric draw. Using the
same default assumptions here (rather than separate hardcoded literals)
keeps this table from drifting out of sync with the UI's own seeded
defaults.
"""

from __future__ import annotations

import random
from datetime import date

from retirement_planner.scenario import ASSET_CLASSES, DEFAULT_MARKET_ASSUMPTIONS, AssetClass, cholesky_lower
from retirement_planner.tax import SourcedFigure

_SYNTHETIC_SERIES_SEED = 1926  # fixed, independent of caller seeds -- see module docstring
_FIRST_YEAR = 1926
_LAST_YEAR = 2025


def _build_synthetic_series() -> dict[int, dict[AssetClass, float]]:
    """Builds the module-docstring's synthetic placeholder 8-asset-class
    return schedule, keyed by calendar year, deterministically from
    _SYNTHETIC_SERIES_SEED -- 8 independent rng.gauss(0,1) draws per year
    in ASSET_CLASSES order, correlated via the same Cholesky transform
    simulation/returns.py's own live parametric draw uses, scaled by
    DEFAULT_MARKET_ASSUMPTIONS's own per-asset-class mean/std."""
    rng = random.Random(_SYNTHETIC_SERIES_SEED)
    lower = cholesky_lower(DEFAULT_MARKET_ASSUMPTIONS.correlation_matrix)
    schedule: dict[int, dict[AssetClass, float]] = {}
    for year in range(_FIRST_YEAR, _LAST_YEAR + 1):
        independent_draws = [rng.gauss(0.0, 1.0) for _ in ASSET_CLASSES]
        correlated_draws = [sum(lower[i][k] * independent_draws[k] for k in range(i + 1)) for i in range(len(ASSET_CLASSES))]
        year_returns: dict[AssetClass, float] = {}
        for index, asset_class in enumerate(ASSET_CLASSES):
            assumptions = DEFAULT_MARKET_ASSUMPTIONS.asset_classes[asset_class]
            year_returns[asset_class] = assumptions.mean_real + assumptions.std_real * correlated_draws[index]
        schedule[year] = year_returns
    return schedule


HISTORICAL_RETURNS: SourcedFigure[dict[AssetClass, float]] = SourcedFigure(
    name="historical_annual_real_returns",
    schedule=_build_synthetic_series(),
    citation=(
        "SYNTHETIC PLACEHOLDER -- not an actual historical return series. Intended "
        "eventual source: real broad-market indices for each of the 8 asset classes, "
        "annual real returns, ~1926-present "
        "(docs/initial_requirement.md §10 Open Question; exact series and date range "
        "not yet selected)."
    ),
    last_verified=date(2026, 8, 28),
    verified=False,
)
