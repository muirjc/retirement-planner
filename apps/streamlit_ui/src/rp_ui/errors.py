"""One exception type per 007 error shape (research.md §4, data-model.md
§ Error types). Every page script catches these specifically -- never a
bare `except Exception` -- so FR-007/FR-015's per-reason distinguishable
message stays a type-level guarantee, not a page-script-level
string-matching concern. See contracts/ui-pages.md for the exact
per-type message each page renders.
"""

from __future__ import annotations


class RpUiError(Exception):
    """Common base for every typed error api_client.py can raise. Exists
    for organization only -- page scripts still catch the specific type
    they know how to render a message for, per data-model.md's own note."""


class ScenarioNotFoundError(RpUiError):
    """007 returned 404 {"error": "no_such_scenario", "name": ...}."""

    def __init__(self, *, name: str) -> None:
        self.name = name
        super().__init__(f"No such scenario: {name!r}")


class InvalidScenarioError(RpUiError):
    """007 returned 422 {"error": "invalid_scenario", "reason": ...}."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid scenario: {reason}")


class BlockingValidationError(RpUiError):
    """007 returned 422 {"error": "blocking_validation_flags", "flags": [...]}.

    flags is a list of {field, message, severity} dicts -- the same shape
    001's ValidationFlag renders to via to_jsonable()."""

    def __init__(self, *, flags: list[dict]) -> None:
        self.flags = flags
        super().__init__(f"{len(flags)} blocking validation flag(s)")


class UnknownReferenceValueError(RpUiError):
    """007 returned 422 {"error": "unknown_reference_value", "field": ..., "value": ...}."""

    def __init__(self, *, field: str, value: str) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Unrecognized value for {field!r}: {value!r}")


class UnsupportedTaxYearError(RpUiError):
    """007 returned 422 {"error": "unsupported_tax_year", "figure_name": ...,
    "requested_year": ..., "documented_years": [...]}. Added after a real
    run against the Run Simulation page's unedited reference_tax_year
    placeholder (1900) surfaced as a bare "HTTP 500" -- 002's own figure
    schedules only cover a bounded range of years; a year outside it is a
    422, not a server error."""

    def __init__(self, *, figure_name: str, requested_year: int, documented_years: list[int]) -> None:
        self.figure_name = figure_name
        self.requested_year = requested_year
        self.documented_years = documented_years
        super().__init__(f"{figure_name!r} has no documented value for tax year {requested_year}")


class PathIndexOutOfRangeError(RpUiError):
    """007 returned 422 {"error": "path_index_out_of_range", "requested": ...,
    "path_count": ...} -- 015-per-account-projection-detail's Detail path
    index override pointed past however many paths the run actually has."""

    def __init__(self, *, requested: int, path_count: int) -> None:
        self.requested = requested
        self.path_count = path_count
        super().__init__(f"Path index {requested} is out of range (this run has {path_count} path(s))")


class SurvivalCurveAgeOutOfRangeError(RpUiError):
    """007 returned 422 {"error": "survival_curve_age_out_of_range",
    "person_name": ..., "age": ...} -- rp-9vl's opt-in survival-adjusted
    scoring only covers ages 50-110 (simulation.survival_data.SURVIVAL_TABLE's
    illustrative curves); this household's ages/horizon reach outside that
    range for the named member."""

    def __init__(self, *, person_name: str, age: int) -> None:
        self.person_name = person_name
        self.age = age
        super().__init__(f"No survival curve coverage for {person_name!r} at age {age}")


class CostBudgetExceededError(RpUiError):
    """007 returned 413 {"error": "estimated_cost_exceeds_budget", "estimated_seconds": ..., "budget_seconds": ...}."""

    def __init__(self, *, estimated_seconds: float, budget_seconds: float) -> None:
        self.estimated_seconds = estimated_seconds
        self.budget_seconds = budget_seconds
        super().__init__(
            f"Estimated cost {estimated_seconds:.0f}s exceeds budget {budget_seconds:.0f}s"
        )


class BackendUnreachableError(RpUiError):
    """A connection/timeout failure reaching 007 at all -- distinct from a
    recognized rejection reason (research.md §4, Edge Cases)."""

    def __init__(self, *, underlying: Exception) -> None:
        self.underlying = underlying
        super().__init__(f"Could not reach the backend: {underlying}")


class UnexpectedBackendError(RpUiError):
    """Any non-2xx response api_client.py doesn't recognize as one of
    007's documented error shapes."""

    def __init__(self, *, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Unexpected response from backend: HTTP {status_code}")
