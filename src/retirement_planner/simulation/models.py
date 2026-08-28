"""Shared simulation-engine data model.

These dataclasses are the locked public shape described in
specs/005-simulation-engine/contracts/simulation-api.md ("Data types"
section) and specs/005-simulation-engine/data-model.md. Types are imported
from retirement_planner.comparison and retirement_planner.tax rather than
redefined, continuing those features' conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from retirement_planner.comparison import PlanProjection, StrategyConfiguration
from retirement_planner.tax import FigureUsage

GenerationMode = Literal["parametric", "historical_bootstrap"]


@dataclass
class ReturnPath:
    """data-model.md § ReturnPath. Satisfies
    retirement_planner.comparison.models.ReturnSchedule via
    return_for_plan_year() (research.md §1)."""

    start_plan_year: int
    annual_returns: list[float]
    generation_mode: GenerationMode
    figures_used: list[FigureUsage] = field(default_factory=list)

    def return_for_plan_year(self, plan_year: int) -> float:
        """Returns annual_returns[plan_year - start_plan_year]. A
        plan_year outside the covered range is a caller precondition
        violation (data-model.md § ReturnPath) -- raises IndexError."""
        return self.annual_returns[plan_year - self.start_plan_year]


@dataclass
class StressScenario:
    """data-model.md § StressScenario."""

    magnitude: float
    duration_years: int
    start_plan_year: int


@dataclass
class SurvivalCurve:
    """data-model.md § SurvivalCurve. Purpose-built rather than a reuse of
    retirement_planner.tax.SourcedFigure, since a survival curve is keyed
    by age, not tax year (research.md §5)."""

    person_name: str
    probabilities_by_age: dict[int, float]
    citation: str
    last_verified: date
    verified: bool

    def survival_probability(self, age: int) -> float:
        """Returns probabilities_by_age[age]. Raises KeyError if age is
        not documented -- never interpolates or falls back (mirrors
        SourcedFigure.value_for_year()'s no-fallback discipline)."""
        return self.probabilities_by_age[age]

    def usage(self) -> FigureUsage:
        """Snapshots this curve's citation metadata, mirroring
        SourcedFigure.usage_for_year()'s shape (research.md §5)."""
        return FigureUsage(
            name=f"survival_curve_{self.person_name}",
            citation=self.citation,
            last_verified=self.last_verified,
            verified=self.verified,
        )


@dataclass
class PercentileBand:
    """data-model.md § PercentileBand."""

    plan_year: int
    percentiles: dict[float, float]


@dataclass
class SimulationRun:
    """data-model.md § SimulationRun."""

    candidate_label: str
    strategy: StrategyConfiguration
    state: str
    path_results: list[PlanProjection]
    success_rate: float
    percentile_bands: list[PercentileBand]
    survival_adjusted_success_rate: float | None
    figures_used: list[FigureUsage] = field(default_factory=list)


ComparisonAxis = Literal["state", "roth_conversion_strategy", "withdrawal_sequencing", "claiming_age_grid"]


@dataclass
class SimulationComparisonResult:
    """data-model.md § SimulationComparisonResult."""

    axis: ComparisonAxis
    return_paths: list[ReturnPath]
    runs: list[SimulationRun]
