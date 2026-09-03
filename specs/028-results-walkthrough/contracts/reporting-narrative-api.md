# Contract: `retirement_planner.reporting.narrative` + POST /simulations addition

This is a library plus one additive web-API field — the "contract" is (1) the public Python
interface `narrative.py` exposes for `services/bff` to call, and (2) the one new field
`POST /simulations` adds to its existing response. Anything not listed here is an internal
implementation detail. See [data-model.md](../data-model.md) for field-level meaning of every
type below; this contract lists shape and call signature only.

Module: `retirement_planner.reporting` (extends the existing re-export list from `models` and
`narrative` — see [plan.md](../plan.md) Project Structure).

## Additive change to `retirement_planner.reporting.aggregation` (research.md §4)

```python
# aggregation.py -- rename only, behavior unchanged:
#   _unverified_figure_names -> unverified_figure_names
# Every existing call site inside aggregation.py updated to the new name.
# reporting/__init__.py -- added to __all__ and re-exported.

def unverified_figure_names(figures_used: list[FigureUsage]) -> list[str]:
    """Unchanged from aggregation's original _unverified_figure_names():
    deduplicates by name (not (name, last_verified)) and sorts. narrative.py
    calls this once per plan year, over that year's own figures_used, to
    populate YearStory.unverified_figure_names (US3/FR-011)."""
```

## Data types (`models`, additive — see data-model.md)

```python
@dataclass
class NarrativeEntry:
    driver_key: str        # one of the closed v1 set (data-model.md) or "baseline"
    label: str
    explanation: str
    amounts: dict[str, float]

@dataclass
class YearStory:
    plan_year: int
    tax_year: int
    member_ages: dict[str, int]   # person_name -> age in tax_year
    entries: list[NarrativeEntry]  # never empty (FR-005)
    unverified_figure_names: list[str] = field(default_factory=list)  # US3/FR-011

@dataclass
class RunNarrative:
    selected_path_index: int
    years: list[YearStory]         # one per plan year of the selected path, ascending order
```

## Operations (`narrative`)

```python
def select_representative_path(run: SimulationRun) -> int:
    """FR-001: the index into run.path_results whose PlanOutcome.ending_balance
    is numerically closest to run.percentile_bands[-1].percentiles[0.50] (the
    final plan year's median ending balance across every path). Ties broken
    by the lowest index. When run.path_results has length 1, returns 0
    without consulting percentile_bands at all (research.md §4)."""

def build_year_stories(
    projection: PlanProjection,       # from retirement_planner.comparison
    household: Household,             # from retirement_planner.scenario
    reference_tax_year: int,
) -> list[YearStory]:
    """FR-002/FR-003/FR-005: walks projection.years pairwise (this year vs.
    the prior; plan year 1 vs. its own starting values) detecting the v1
    driver set (research.md §3) via each PlanYearProjection's already-
    computed fields -- no new tax/mechanics/simulation computation
    (FR-004/FR-014). Every plan year produces exactly one YearStory, with a
    single driver_key="baseline" NarrativeEntry when nothing else fired.
    Pure and deterministic: identical projection input -> byte-identical
    output every call (FR-006)."""

def build_narrative_for_run(
    run: SimulationRun,               # from retirement_planner.simulation
    household: Household,
    reference_tax_year: int,
) -> RunNarrative:
    """Composes select_representative_path() + build_year_stories() over
    run.path_results[selected_path_index]. The single entry point BFF
    routes call -- computed once, for the selected path only (FR-008: no
    per-path computation, no new round trip)."""
```

**Pre/postconditions**: `run.path_results` MUST be non-empty (guaranteed by
`run_simulation()`'s own contract — a `SimulationRun` is never constructed with zero paths).
`build_narrative_for_run()` never raises for any valid `SimulationRun`; every plan year of the
selected path always yields a `YearStory` (FR-005).

## Additive change to `POST /simulations` (`services/bff`)

No new endpoint, no new request field (FR-008). `SimulationRequest`'s existing shape is
unchanged. The response gains exactly one key:

```jsonc
// POST /simulations response (existing "run"/"summary"/"account_detail" keys unchanged):
{
  "run": { /* unchanged */ },
  "summary": { /* unchanged */ },
  "account_detail": [ /* unchanged */ ],
  "narrative": {
    "selected_path_index": 12,
    "years": [
      {
        "plan_year": 1,
        "tax_year": 2026,
        "member_ages": {"you": 62},
        "entries": [
          {
            "driver_key": "baseline",
            "label": "...",
            "explanation": "...",
            "amounts": {}
          }
        ]
      }
      // ...one entry per plan year of the selected path
    ]
  }
}
```

`narrative` is computed exactly once per request, for the one path `select_representative_path()`
selects — independent of, and unrelated to, the existing `detail_path_index` request field (which
governs `account_detail`'s own, separately-selected path per 015-per-account-projection-detail;
the two selections may point at different path indices and that is expected, not a bug).

## Streamlit UI contract (`apps/streamlit_ui`)

No new HTTP call. `4_Walkthrough.py` reads `st.session_state["run_last_result"]["narrative"]` —
the same dict key `2_Run_Simulation.py`'s existing `run_simulation()` response already populates
into that session-state entry. If `"run_last_result"` is absent from `st.session_state`, the page
renders guidance to run a simulation first (FR-013) instead of calling any endpoint.
