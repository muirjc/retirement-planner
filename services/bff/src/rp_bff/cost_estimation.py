"""Pre-flight cost estimation for run/comparison/export requests
(FR-018, research.md §5): reject anything projected to exceed the
constitution's performance budget *before* dispatching to 004/005, rather
than letting a request hang.

PER_UNIT_COST_SECONDS was verified against 006's actual measured
reference-scale benchmark before being adopted -- see research.md §5 for
how an earlier, 36x-too-conservative draft value would have caused this
gate to incorrectly reject the reference-scale request SC-003 requires to
succeed.
"""

from __future__ import annotations

PER_UNIT_COST_SECONDS = 0.0001  # 0.1ms per (path x candidate x plan-year)
REJECTION_THRESHOLD_SECONDS = 30.0  # half the constitution's "well under a minute" budget


class CostBudgetExceededError(Exception):
    """Raised when a request's estimated cost exceeds REJECTION_THRESHOLD_SECONDS."""

    def __init__(self, estimated_seconds: float, budget_seconds: float) -> None:
        """Carries the estimate and the budget it exceeded, so a route
        handler can report both in the estimated_cost_exceeds_budget
        response (contracts/bff-api.md)."""
        self.estimated_seconds = estimated_seconds
        self.budget_seconds = budget_seconds
        super().__init__(
            f"estimated cost {estimated_seconds:.1f}s exceeds the {budget_seconds:.1f}s budget"
        )


def estimate_cost_seconds(path_count: int, candidate_count: int, horizon_years: int) -> float:
    """A conservative, linear estimate of a run/comparison request's cost:
    one unit of work per (path, candidate, plan-year) triple."""
    return path_count * candidate_count * horizon_years * PER_UNIT_COST_SECONDS


def check_cost_within_budget(path_count: int, candidate_count: int, horizon_years: int) -> None:
    """Raises CostBudgetExceededError if the estimated cost exceeds
    REJECTION_THRESHOLD_SECONDS; returns None otherwise (FR-018)."""
    estimated = estimate_cost_seconds(path_count, candidate_count, horizon_years)
    if estimated > REJECTION_THRESHOLD_SECONDS:
        raise CostBudgetExceededError(estimated, REJECTION_THRESHOLD_SECONDS)
