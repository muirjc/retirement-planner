# Contract: `retirement_planner.reporting` public API

This is a library, not a network service — the "contract" is the public Python interface this feature exposes for later features (§3.6's remaining consumer, `007` BFF API Service, per `docs/frontend_architecture.md`) to import and build on. Anything not listed here is an internal implementation detail; anything listed here is what downstream features should code against.

Module: `retirement_planner.reporting` (re-exports from `models`, `aggregation`, `export` — see [plan.md](../plan.md) Project Structure).

## Additive change to `retirement_planner.comparison` (research.md §1)

```python
# comparison/projection.py -- rename only, behavior unchanged:
#   _member_age_in_tax_year -> member_age_in_tax_year
#   _deemed_rmd_owner       -> deemed_rmd_owner
# Every existing call site inside projection.py updated to the new names.
# comparison/__init__.py -- both added to __all__ and re-exported.

def member_age_in_tax_year(member: HouseholdMember, tax_year: int, reference_tax_year: int) -> int:
    """Unchanged from 004's original _member_age_in_tax_year(): translates
    member.current_age (accurate as of reference_tax_year) into that
    member's age in an arbitrary tax_year."""

def deemed_rmd_owner(household: Household) -> HouseholdMember:
    """Unchanged from 004's original _deemed_rmd_owner(): the older
    household member (or the sole member) is treated as the deemed owner
    of the household's entire traditional balance for RMD purposes."""
```

## Data types (`models`)

```python
@dataclass
class SummaryStatistics:
    candidate_label: str | None
    success_rate: float | None            # None for a deterministic (004) candidate
    ending_balance: float                  # always populated -- median (Monte Carlo) or single value (deterministic)
    percentile_bands: list[PercentileBand] | None  # None for a deterministic (004) candidate; from retirement_planner.simulation
    median_depletion_age: float | None    # None if nothing depleted
    median_lifetime_tax_paid: float
    unverified_figure_names: list[str]    # always a list, possibly empty -- never None
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Operations (`aggregation`)

```python
def summarize_run(
    run: SimulationRun,               # from retirement_planner.simulation
    household: Household,             # from retirement_planner.scenario
    reference_tax_year: int,
) -> SummaryStatistics:
    """Summarizes one completed SimulationRun (FR-001-FR-004). success_rate
    and percentile_bands are read directly from run's own fields.
    ending_balance is run.percentile_bands[-1].percentiles[0.50].
    median_depletion_age is the median deemed-owner age (via
    deemed_rmd_owner()/member_age_in_tax_year()) across every path in
    run.path_results whose outcome.first_shortfall_plan_year is not None;
    None if no path depleted (FR-003). median_lifetime_tax_paid is the
    median outcome.cumulative_tax_paid across every path, depleted or not
    (FR-002). unverified_figure_names is the deduplicated (by name) set of
    every figure in run.figures_used with verified=False, sorted (FR-004,
    research.md §5). candidate_label is None (this is not part of a
    comparison)."""


def summarize_simulation_comparison(
    comparison: SimulationComparisonResult,  # from retirement_planner.simulation
    household: Household,
    reference_tax_year: int,
) -> list[SummaryStatistics]:
    """Returns [summarize_run(run, household, reference_tax_year) for run
    in comparison.runs], with each result's candidate_label set from that
    run's candidate_label (FR-005, research.md §4). Preserves
    comparison.runs' order exactly."""


def summarize_deterministic_comparison(
    comparison: ComparisonResult,     # from retirement_planner.comparison
    household: Household,
    reference_tax_year: int,
) -> list[SummaryStatistics]:
    """One SummaryStatistics per entry in comparison.projections, in
    order, with candidate_label from projection.strategy.label,
    success_rate and percentile_bands left None (research.md §2),
    ending_balance from projection.outcome.ending_balance,
    median_depletion_age from projection.outcome.first_shortfall_plan_year
    (None if that candidate never fell short), median_lifetime_tax_paid
    from projection.outcome.cumulative_tax_paid (a single value, median of
    one), and unverified_figure_names deduplicated from every
    projection.years[*].figures_used entry (FR-006)."""
```

## Operations (`export`)

```python
def run_to_csv_text(run: SimulationRun) -> str:
    """One row per plan year: plan_year, one column per percentile level
    present in run.percentile_bands[*].percentiles (e.g. p10/p25/p50/p75/p90),
    and has_unverified_figure -- derived from
    run.path_results[0].years[y].figures_used for plan-year index y
    (research.md §6), true iff any figure there has verified=False
    (FR-008, FR-010). Rendered via csv.DictWriter into an io.StringIO;
    returns the resulting text."""


def simulation_comparison_to_csv_text(
    comparison: SimulationComparisonResult,
    household: Household,
    reference_tax_year: int,
) -> str:
    """Calls summarize_simulation_comparison() and renders one row per
    resulting SummaryStatistics: candidate_label, success_rate,
    ending_balance, median_depletion_age, median_lifetime_tax_paid,
    has_unverified_figure (true iff unverified_figure_names is non-empty)
    (FR-009, FR-010)."""


def deterministic_comparison_to_csv_text(
    comparison: ComparisonResult,
    household: Household,
    reference_tax_year: int,
) -> str:
    """Calls summarize_deterministic_comparison() and renders the same row
    shape as simulation_comparison_to_csv_text(), with success_rate always
    blank (every candidate's SummaryStatistics.success_rate is None) since
    every candidate in a deterministic comparison has no rate to report
    (FR-009, FR-010, research.md §2)."""
```

## Consumption expectations for downstream features

- `summarize_run()`/`summarize_simulation_comparison()`/`summarize_deterministic_comparison()` are the entry points a future `007` BFF endpoint should call to embed a summary alongside a raw run/comparison result in an HTTP response — `docs/frontend_architecture.md`'s sketched `POST /simulations` response shape (`{"run": ..., "summary": ...}`) is exactly `summarize_run()`'s output for the `"summary"` key.
- `SummaryStatistics.unverified_figure_names` is the single place a downstream reporting/UI feature should look to render a "needs verification" indicator for a run or comparison at the summary level — it is a deduplicated derivation, not a fresh source of truth, so it never contradicts what a `FigureUsage.verified` flag anywhere in the underlying result already says.
- The CSV exporters return plain `str` — a caller wanting an HTTP file-download response (`007`) wraps this feature's output in whatever response type its own transport layer needs; this feature has no opinion on HTTP headers, content types, or file naming.
- A caller needing `household`/`reference_tax_year` for a `SimulationRun`/`ComparisonResult` it received from elsewhere (e.g. a future `007` endpoint that only stores a scenario's YAML, not these two values separately) is expected to derive them from that same scenario (`Scenario.household`, and the scenario's own configured reference tax year) — this feature does not infer or default either value itself, consistent with `004`/`005` never defaulting them either.
