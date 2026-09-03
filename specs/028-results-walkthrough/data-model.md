# Phase 1 Data Model: Year-by-Year Results Walkthrough

All three dataclasses below are added to `src/retirement_planner/reporting/models.py`, following
that module's existing convention (plain `@dataclass`, docstring pointing back to this file,
`from __future__ import annotations`). None replace or modify any existing type; `PlanYearProjection`,
`SimulationRun`, and every field they carry are unchanged (FR-014).

## NarrativeEntry

One detected driver within a single plan year's story.

| Field | Type | Notes |
|---|---|---|
| `driver_key` | `str` | Stable identifier for the driver kind — one of `"rmd_start"`, `"ss_claiming"`, `"roth_conversion"`, `"withdrawal_source_change"`, `"tax_change"`, `"irmaa_start"`, `"irmaa_basis_switch"`, `"survivor_death"`, `"shortfall"`, or `"baseline"` (the FR-005 fallback when no other driver fired this year). Machine-stable across runs — used by tests to assert "this driver fired exactly on its transition year" without string-matching prose. |
| `label` | `str` | Short human-readable heading for this entry, e.g. `"Required Minimum Distributions began"`. |
| `explanation` | `str` | The plain-language sentence(s) for this driver, referencing the amounts in `amounts` by value (e.g., `"...adding $18,400 to taxable income"`). Deterministic string composition only — no randomness, no external call (Principle II, Principle V). |
| `amounts` | `dict[str, float]` | The specific dollar amount(s) supporting this driver, keyed by a short descriptive name (e.g., `{"rmd_amount": 18400.0}`). Sourced only from fields already present on `PlanYearProjection`/its nested results (FR-004) — this is P2's (rp-bm8.2) only allowed source of numbers, per the parent bead's design. |

**Validation rules**: `driver_key` MUST be one of the closed v1 set above (no free-form keys in
v1). `amounts` MAY be empty only for `driver_key == "baseline"`; every other driver key MUST
carry at least one amount.

## YearStory

The full narrative for one plan year of the selected representative path.

| Field | Type | Notes |
|---|---|---|
| `plan_year` | `int` | Matches `PlanYearProjection.plan_year` for the same year — the join key back to the existing numeric detail already shown elsewhere on the page. |
| `tax_year` | `int` | Matches `PlanYearProjection.tax_year` — carried through so the UI/tests don't need to re-derive it from `plan_year`. |
| `member_ages` | `dict[str, int]` | Each household member's age in this plan year's `tax_year`, via the existing `member_age_in_tax_year()` (006-reporting-aggregation) — no new age-translation logic (per parent bead's design note). |
| `entries` | `list[NarrativeEntry]` | Every driver detected for this year, in the fixed v1 priority order (RMD start, SS claiming, Roth conversion, withdrawal-source change, tax change, IRMAA start/basis switch, survivor death, shortfall). Never empty — exactly one `NarrativeEntry` with `driver_key == "baseline"` when nothing else fired (FR-005). |
| `unverified_figure_names` | `list[str]`, defaults to `[]` | This plan year's own deduplicated, sorted list of unverified figure names, derived from `PlanYearProjection.figures_used` the same way `SummaryStatistics.unverified_figure_names` already is (research.md §4) — always a list, possibly empty, never `None` (US3/FR-011). Defaults to an empty list (mirroring `SummaryStatistics`'s own `field(default_factory=list)`), so `build_year_stories()` can populate it independently of the entry-detection logic (research.md §4 — populated by a task within the US3 slice, not required for US1's own driver-detection to be complete). |

**Validation rules**: `entries` MUST have length ≥ 1 for every `YearStory` (FR-005 — no plan year
is ever left without a story).

## RunNarrative

The complete walkthrough for one simulation run.

| Field | Type | Notes |
|---|---|---|
| `selected_path_index` | `int` | The representative path's index into `run.path_results` (FR-001/FR-006) — index into the *same* list the run's other per-path detail already lives in, not a separate identifier space. |
| `years` | `list[YearStory]` | One entry per plan year of the selected path's projection, in ascending `plan_year` order, spanning the full projection (FR-002) — length equals `len(run.path_results[selected_path_index].years)`. |

**Validation rules**: `years` MUST cover every plan year of the selected path's projection, with
no gaps and no duplicates (FR-002). Given identical scenario configuration and seed,
`selected_path_index` and every `YearStory`/`NarrativeEntry` field in `years` MUST be
byte-identical across repeated calls (FR-006/SC-002).

## Relationships

```text
SimulationRun (005-simulation-engine, unchanged)
  └─ path_results: list[PlanProjection]
        └─ selected by select_representative_path(run) -> selected_path_index
              └─ build_year_stories(projection, household, reference_tax_year) -> list[YearStory]
                    ├─ walks projection.years pairwise (prior vs. current) to detect drivers
                    └─ produces RunNarrative(selected_path_index, years)

RunNarrative  ─┐
YearStory      ├─ new, additive; reference existing types (PlanYearProjection fields,
NarrativeEntry┘   member_age_in_tax_year(), WITHDRAWAL_STRATEGIES) but do not modify them
```

No state transitions apply — every dataclass here is an immutable snapshot produced once per
request, not a mutated or persisted entity (Storage: N/A per plan.md's Technical Context).
