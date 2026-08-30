# Implementation Plan: Per-Account Year-by-Year Projection Detail

**Branch**: `015-per-account-projection-detail` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-per-account-projection-detail/spec.md`

## Summary

Adds year-by-year, per-account detail (balance, RMD amount, withdrawal
amount, plus per-member Social Security benefit received) to a
simulation result (one representative Monte Carlo path) and to each
candidate in a comparison — surfaced as a new Streamlit UI table.
Extends `011-per-owner-accounts`'s own already-shipped precedent (a fixed
share, computed once from the scenario's initial per-account data,
applied to whatever the pooled engine already produces each year) down
from the member level to the individual account level, rather than
rearchitecting the engine's pooled `AccountBalances` arithmetic — which
`011`'s own `research.md` already evaluated and rejected for lacking any
principled per-account withdrawal/conversion attribution rule (no cost
basis, no lot-level tracking in this project's schema). Three pieces of
data the engine already computes correctly today but discards before
returning (each member's own RMD amount, each member's own gross Social
Security benefit, and each inherited account's own year-by-year
snapshot) are retained as new `PlanYearProjection` fields — a purely
additive change to `004`'s locked data shape, zero change to any existing
field's value. A new `reporting/account_attribution.py` module derives
per-*ordinary*-account balances and withdrawal amounts from those pooled
totals via a fixed per-account share, computed once from
`Scenario.accounts` and labeled per-row as `"independently_tracked"`
(inherited accounts, exact) vs. `"fixed_share_of_pooled_total"` (ordinary
accounts, an explicit apportionment) — never presenting one as the
other, per the constitution's Accuracy-Over-Cleverness principle.
`services/bff`'s comparison routes, which today discard the full
`ComparisonResult`/`SimulationComparisonResult` after summarizing it,
gain a new `account_detail` response field computed for exactly one
selected path (default path 0) per candidate — never for every Monte
Carlo path, preserving the existing performance budget by construction.

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter
floor as `001`–`014` (`pyproject.toml` still pins `>=3.11`).

**Primary Dependencies**: No new third-party runtime dependency anywhere
in the stack. New in-repo dependencies: a new core-library module
(`retirement_planner.reporting.account_attribution`, depending only on
`retirement_planner.scenario.Account`/`Household` and
`retirement_planner.comparison`'s existing `PlanProjection` shape — the
same dependency direction `reporting/aggregation.py` already has); a new
BFF module (`rp_bff.account_detail`, depending on the new reporting
module plus `rp_bff.serialization.to_jsonable()`); a new Streamlit
component (`rp_ui.account_table`, depending only on already-BFF-returned
JSON, per `rp_ui.charts`'s existing "pure display" convention).

**Storage**: None new. No new persisted field — `Scenario.accounts`
(already persisted YAML) is the only input the new attribution module
needs beyond what `run_plan_projection()` already returns.

**Testing**: pytest, continuing `001`–`014`'s convention across all four
layers (core, BFF, UI, e2e). New tests are invariant-based, not
hand-calculated-dollar-figure-based (Development Workflow gate below) —
e.g. "per-account balances of a type sum to exactly that type's pooled
balance," not an assertion pinned to a specific dollar amount picked with
no derivation.

**Target Platform**: Same as `001`–`014`: local developer/user machine,
offline, BFF bound to `127.0.0.1` only.

**Project Type**: Continues the existing three-layer monorepo (core
library / BFF / UI) — no new package, no new subpackage boundary crossed
(the new core module lives inside the already-existing `reporting`
subpackage, itself already the "depends on everything else" layer).

**Performance Goals**: The new attribution derivation
(`attribute_plan_projection()`) runs over exactly one `PlanProjection` —
one candidate's one selected path — per request, never once per Monte
Carlo path. For a 3,000–5,000-path simulation this is a ~5,000x-smaller
computation than the simulation itself, so it cannot meaningfully affect
the existing performance budget (Constitution Principle VI) regardless
of how many paths a run has; this is a structural guarantee (the
function's own input shape), not a discipline that could regress later.

**Constraints**: Zero change to any existing computed value — every new
field on `PlanYearProjection` is additive with a `field(default_factory=...)`
default, and every existing construction call site, test assertion, and
downstream consumer (BFF serialization, CSV export, UI rendering) that
doesn't opt into the new fields continues to see byte-identical output.
The account-level apportionment share is computed once, from the
scenario's *starting* per-account balances only, and held fixed for the
life of a run (mirroring `011`'s own `traditional_ownership_shares`
precisely) — it is never re-derived from a later year's balances, which
would make the same account's attributed share drift for reasons that
have nothing to do with anything the user configured.

**Scale/Scope**: 4 new fields on one existing dataclass
(`PlanYearProjection`), 1 new core module (`account_attribution.py`, ~4
new dataclasses/functions), 1 new BFF module (`account_detail.py`) plus
2 existing route changes (`comparisons.py`, `simulations.py`), 1 new UI
component (`account_table.py`) plus 2 existing page insertions
(`2_Run_Simulation.py`, `3_Compare.py`). No change to `compute_rmd()`,
`withdrawal_sequencing.py`, `roth_conversion.py`, or any currently-locked
contract (`specs/003-*`, `specs/004-*`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness** — ✅ PASS. This feature's entire design
  is organized around this principle: every per-account figure is
  labeled `"independently_tracked"` or `"fixed_share_of_pooled_total"`
  (data-model.md § AccountYearDetail), and the one known accuracy gap
  this feature cannot close (a Roth conversion possibly apportioned to a
  Roth account the converting member doesn't actually own, since no
  cost-basis/per-member Roth ownership tracking exists) is documented in
  spec.md's Assumptions rather than silently absorbed — the same
  disclosure discipline `011`'s own research.md already set for the
  analogous per-member RMD apportionment.
- **II. Reproducibility** — ✅ PASS. `compute_account_shares()` is a pure
  function of `Scenario.accounts` (no randomness); `attribute_plan_
  projection()` is a pure function of an already-computed, already-
  deterministic `PlanProjection`. Selecting a Monte Carlo path by a fixed
  `detail_path_index` (default `0`) is itself deterministic — same
  scenario, same seed, same path index always shows the same detail.
- **III. Auditability** — ✅ PASS. This feature doesn't introduce a new
  `SourcedFigure` (no new externally-sourced regulatory figure), so
  citation/verification tracking is unaffected — but it extends the
  *same* transparency discipline to a different kind of provenance
  question ("was this number tracked or apportioned") via the
  `attribution` field, rather than inventing an unrelated disclosure
  mechanism.
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. The new
  attribution logic lives in one new, sibling module
  (`reporting/account_attribution.py`), not a branch inside
  `run_plan_projection()`'s or `compute_plan_year_mechanics()`'s locked
  bodies — the same "new module, not a widened core function" pattern
  `012`'s own `inherited_rmd.py` already established for an analogous
  "needs its own concept, not a core-engine branch" situation.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. Pure
  computation over already-in-memory data; no I/O of any kind.
- **VI. Performance Budget** — ✅ PASS. See Performance Goals above — the
  attribution computation is structurally bounded to one path regardless
  of simulation scale.

**Technology & Architecture Constraints:**

- *"Config as data, not code"* — Unaffected; no new scenario input field.
- *Paired-draw comparison is the standard pattern* — Unaffected; this
  feature adds a reporting-layer derivation over comparison results
  already produced by the existing paired-draw machinery, it doesn't
  touch how paths/candidates are compared.
- *Scope boundary with the working document* — N/A, not implicated.

**Development Workflow & Quality Gates:**

- *Regression baseline* — Required and structurally guaranteed: every new
  field is additive with a default, so every existing reference
  scenario/fixture must produce byte-identical output before and after
  this feature for every field that already existed.
- *Verified-figure gate* — N/A; no new `SourcedFigure` is introduced.
- *Unit test coverage for numeric primitives* — Required: the
  attribution module's own arithmetic (share computation, balance/
  withdrawal apportionment, RMD sub-allocation) gets invariant tests
  (sums-to-the-pooled-total, exactness in the common single-account-per-
  member case, zero-division safety) rather than hand-picked dollar
  figures, per spec.md's own testing approach and this project's existing
  precedent for "the math is under test, not a magic number."

**Post-Phase 1 re-check**: Confirmed after generating research.md,
data-model.md, contracts/{reporting-api,bff-api}.md addenda, and
quickstart.md — no new violations. Keeping the apportionment as an
explicitly-labeled reporting-layer derivation (rather than folding it
into the engine's own pooled arithmetic) is what keeps Principle I
satisfied without inventing a withdrawal-attribution rule the engine
itself would then implicitly assert as fact.

## Project Structure

### Documentation (this feature)

```text
specs/015-per-account-projection-detail/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
│   ├── reporting-api.md   # New account_attribution.py public shape
│   └── bff-api.md          # account_detail field + detail_path_index param addenda
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── comparison/
│   ├── models.py              # PlanYearProjection: +member_rmd_amounts,
│   │                           # +member_social_security_benefits,
│   │                           # +inherited_account_balances,
│   │                           # +inherited_account_distributions (all dict, default {})
│   └── projection.py           # run_plan_projection(): capture per-member RMD dict and
│                                # per-member SS benefit dict (currently summed-then-
│                                # discarded); capture inherited-account snapshots at the
│                                # existing per-inherited-account loop. No existing value changes.
└── reporting/
    ├── account_attribution.py  # NEW — AccountShare, AccountYearDetail, PlanYearAccountDetail,
    │                            # compute_account_shares(), attribute_plan_projection()
    └── __init__.py               # +export the above alongside summarize_run() etc.

services/bff/src/rp_bff/
├── account_detail.py            # NEW — build_account_detail_for_projection(),
│                                  # build_account_detail_for_run() (bounds-checks
│                                  # detail_path_index, 422 on out-of-range)
├── schemas.py                    # SimulationRequest, ComparisonRequest: +detail_path_index: int | None = None
└── routes/
    ├── simulations.py            # +account_detail in POST /simulations response
    └── comparisons.py            # +account_detail per candidate in both comparison routes'
                                   # responses (result was computed and discarded before;
                                   # now also passed to account_detail.py before discarding)

apps/streamlit_ui/
├── src/rp_ui/
│   └── account_table.py         # NEW — render_account_table(account_detail: dict) -> None
└── pages/
    ├── 2_Run_Simulation.py      # +render_account_table() call after render_verification_indicator();
    │                             # +"Detail path index" number_input in Advanced overrides
    └── 3_Compare.py              # +per-candidate st.expander wrapping render_account_table()

tests/unit/
├── comparison/
│   └── test_projection.py       # +invariant tests for the 4 new PlanYearProjection fields
└── reporting/
    └── test_account_attribution.py  # NEW — share/apportionment invariant tests

services/bff/tests/unit/
└── test_account_detail.py       # NEW — shape + detail_path_index bounds-validation tests

apps/streamlit_ui/tests/unit/
└── test_account_table.py        # NEW — literal-fixture-dict rendering tests

e2e/
├── test_run_simulation_page.py  # +assert the new table renders
└── test_compare_page.py          # +assert each candidate's expander/table renders
```

**Structure Decision**: Continues `001`–`014`'s existing package layout
with two new files inside already-existing packages (`reporting/`,
`rp_bff/`, `rp_ui/`) and no new package or subpackage boundary. Every
existing file this feature touches gets an additive change (new field,
new optional parameter, new response key) — no existing function
signature loses a parameter or changes an existing parameter's meaning,
and no currently-locked contract (`specs/003-*`, `specs/004-*`) is
modified, only extended, the same way `010`'s and `012`'s own addenda to
`004`'s contract already were.

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) —
this section is not needed.*
