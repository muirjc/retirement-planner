"""Actuarial survival curves for run_simulation()'s optional
survival-adjusted success metric (FR-017, research.md §5).

SURVIVAL_TABLE below is an **illustrative placeholder**, not sourced from an
actual published period life table -- consistent with Constitution
Principle V (Offline-First, No Runtime Network Dependency), this feature
cannot fetch a real table at runtime or at authoring time in this
environment. `verified=False` on every SurvivalCurve reflects that honestly
(Principle III) -- these curves MUST NOT be marked verified until replaced
with a real, cited table (e.g. an SSA-style period life table) and confirmed
against a primary source, mirroring the precedent
simulation/historical_data.py's HISTORICAL_RETURNS already set.

Two roles are provided ("primary", "spouse") for a caller to map onto its
HouseholdMembers' person_name (per FR-018, a caller must supply one curve
per household member it wants survival-adjusted scoring for).
"""

from __future__ import annotations

from datetime import date

from .models import SurvivalCurve

_CITATION = (
    "ILLUSTRATIVE PLACEHOLDER -- not an actual published life table. Intended "
    "eventual source: a standard period life table (e.g. an SSA-style table), "
    "per specs/005-simulation-engine/research.md §5."
)
_LAST_VERIFIED = date(2026, 8, 28)


def _build_illustrative_curve() -> dict[int, float]:
    """A smooth, monotonically-decreasing illustrative survival curve from
    age 50 (certain survival) to age 110 (near-zero), using a simple
    logistic decline centered near age 85 -- plausible in shape, not a real
    mortality table."""
    midpoint_age = 85.0
    steepness = 0.15
    probabilities: dict[int, float] = {}
    for age in range(50, 111):
        probabilities[age] = 1.0 / (1.0 + pow(2.718281828, steepness * (age - midpoint_age)))
    return probabilities


SURVIVAL_TABLE: dict[str, SurvivalCurve] = {
    "primary": SurvivalCurve(
        person_name="primary",
        probabilities_by_age=_build_illustrative_curve(),
        citation=_CITATION,
        last_verified=_LAST_VERIFIED,
        verified=False,
    ),
    "spouse": SurvivalCurve(
        person_name="spouse",
        probabilities_by_age=_build_illustrative_curve(),
        citation=_CITATION,
        last_verified=_LAST_VERIFIED,
        verified=False,
    ),
}
