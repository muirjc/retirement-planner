# Implementation Plan: Early-Withdrawal Penalty (Pre-59.5)

**Branch**: `020-early-withdrawal-penalty` | **Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/020-early-withdrawal-penalty/spec.md`

## Summary

Fixes rp-8z0: no reference to age 59.5, the 10% early-withdrawal penalty, or 72(t)/SEPP exists
anywhere in this codebase, despite the tool's own reference use case starting household members at
ages 58/60 — squarely pre-59.5 — while drawing from Traditional. This feature adds a new cited tax
module, `tax/early_withdrawal_penalty.py` (mirroring `tax/niit.py`'s shape exactly: a flat-rate
surtax on a computed base), with one pure function computing 10% of a plan year's **combined
taxable early-distribution base** — the sum of (a) each under-59.5 household member's own share
(via `traditional_ownership_shares`, `011`'s existing per-owner RMD attribution) of that year's
voluntary (non-RMD) Traditional withdrawal, and (b) that year's own
`PlanYearProjection.unseasoned_roth_withdrawal` (`019`'s Roth-ladder flag, consumed as-is — this
feature never re-derives Roth lot seasoning or re-checks age for it). Unlike `IrmaaResult`'s and
`NiitResult`'s own amounts (found during this feature's specification, `rp-yqf`, to be reported but
never actually funded — a bug filed and fixed separately, not here), this feature's own penalty
**is** added to the plan year's actually-funded tax obligation from the start. New
`PlanYearProjection.early_withdrawal_penalty`/`PlanOutcome.cumulative_early_withdrawal_penalty_paid`
fields mirror `irmaa`/`niit`'s existing reporting shape exactly, including the same
`reporting`/`apps/streamlit_ui` ripple `010` originally established for those two figures (a new
`median_lifetime_early_withdrawal_penalty_paid` summary field, CSV column, and narration line).

This is **not** a purely-additive opt-in feature like `018`/`019` — it is an accuracy correction
that will change real computed output (ending balances, shortfall) for any existing scenario with a
member under 60 drawing Traditional funds, including this tool's own reference use case. This
mirrors `016`'s own precedent (the Social Security claiming-age adjustment) more than `017`'s/`018`'s/`019`'s
own "confirmed zero existing fixtures need correction" precedent — research.md documents the
expected regression triage approach rather than claiming non-disruption.

## Technical Context

**Language/Version**: Python 3.11+ (matches this project's existing constraint; no new dependency).

**Primary Dependencies**: None new — reuses `retirement_planner.tax.SourcedFigure`/`FigureUsage`
(already imported by every other cited-figure module), stdlib only.

**Storage**: N/A — in-memory dataclasses, same as every existing feature. No new scenario YAML
field — this feature has no new input surface, only new output (mirrors `019`'s own precedent: an
always-on accuracy correction, not an opt-in one, so no BFF/UI *input* changes either).

**Testing**: `pytest` (`tests/unit/tax/test_early_withdrawal_penalty.py` (new),
`tests/unit/comparison/test_projection.py`, `tests/unit/reporting/test_aggregation.py`,
`tests/unit/reporting/test_export.py`, `apps/streamlit_ui/tests/unit/test_narration.py`), mirroring
`010`'s own suite layout for IRMAA/NIIT plus every downstream reporting/UI consumer. Given the
regression-surface note above, running the **full** four-suite quality gate early and often during
implementation (not just at the end) is part of this feature's own process, not deferred polish.

**Target Platform**: Same as the rest of this project — a single-user, offline-first CLI/library
plus its BFF/Streamlit UI (constitution Principle V).

**Project Type**: Library feature (core `retirement_planner` package) with mechanical ripple into
`reporting` and `apps/streamlit_ui` (mirroring `010`'s own exact touchpoints for a new lifetime-cost
figure) — no `services/bff` code change (it already passes `PlanYearProjection`/`PlanOutcome`
through generically, confirmed during `019`'s own investigation) and no new scenario input surface.

**Performance Goals**: No material change — the new computation is O(household size) per plan year
(one proportional split across at most two members), materially cheaper than a Monte Carlo path's
own return-draw cost; Constitution Principle VI's Monte Carlo budget is unaffected.

**Constraints**: Must preserve reproducibility (Principle II) — the new logic is pure/deterministic
(no randomness, no I/O). Must not apply to any RMD-mandated distribution or inherited-account
distribution (FR-003, FR-004, SC-004) — both real statutory exclusions, not simplifications. Must
leave a household with every member 60+ and no unseasoned Roth withdrawal completely unaffected
(FR-010, SC-002).

**Scale/Scope**: One new module (`tax/early_withdrawal_penalty.py`, one public function, one new
cited figure), one new result type (`EarlyWithdrawalPenaltyResult`) in `tax/models.py`, one modified
function (`comparison/projection.py::run_plan_projection()`, additive per-year computation plus
funding), two new fields (`PlanYearProjection.early_withdrawal_penalty`,
`PlanOutcome.cumulative_early_withdrawal_penalty_paid`), and the `010`-established reporting/UI
ripple (`reporting/models.py`, `reporting/aggregation.py`, `reporting/export.py`,
`apps/streamlit_ui/src/rp_ui/narration.py`). `docs/BRD.md` updated. No `services/bff`,
`scenario/`, or Streamlit *input*-widget changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | This feature removes a silent gap (a real, often-material cost the tool's own reference use case would actually incur, entirely unmodeled today) rather than introducing a new one. Its own simplifications — no 72(t)/SEPP, no statutory exception beyond age 59.5 — are documented in spec.md Assumptions and carried into `docs/BRD.md` (FR-011), not silently absorbed. Explicitly does NOT replicate the IRMAA/NIIT funding gap found during this feature's own specification (filed separately, `rp-yqf`) — this feature's own new cost is funded correctly from the start. | PASS |
| II. Reproducibility | The new computation is pure/deterministic (no randomness, no I/O); identical scenario + seed still yields identical output. | PASS |
| III. Auditability | The new 10% rate figure carries a citation and `last_verified` date via `SourcedFigure`/`FigureUsage`, flowing into `PlanYearProjection.figures_used` every plan year (mirrors NIIT's own "always computed, always cited, even when the result is 0.0" precedent). `verified=True` only set after the citation is actually cross-checked at implementation time, per the constitution's verified-figure gate. | PASS |
| IV. Extensibility Through Module Interfaces | New logic lives behind one new function in one new module, called from exactly one place in the simulation core (`run_plan_projection()`'s per-year loop), mirroring `niit.py`'s/`irmaa.py`'s own module shape and call-site pattern precisely. | PASS |
| V. Offline-First | No network dependency introduced. | PASS |
| VI. Performance Budget | O(household size) per plan year; no regression to the Monte Carlo budget (Technical Context). | PASS |
| Paired-draw comparison standard | No comparison axis is added or restructured — every existing `compare_*()` function is unchanged; only the funded/reported dollar amounts for an affected candidate change, exactly like every other tax-computation correction this loop already applies identically across every candidate. | PASS |
| Config as data, not code | N/A — this feature adds no new scenario-configurable value; the 10% rate itself is a fixed statutory constant, cited like every other such constant (`RMD_START_AGE`, `SS_CLAIMING_AGE_ADJUSTMENT`, `NIIT`'s own rate/thresholds), not something a household configures. | PASS |

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/020-early-withdrawal-penalty/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── tax-api.md            # addendum to 002/010 (new operation)
│   ├── comparison-api.md     # addendum to 004/010/011/012/018/019 (new fields, new per-year step)
│   └── reporting-api.md      # addendum to 006/010 (new summary field, CSV column)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── tax/
│   ├── models.py                       # + EarlyWithdrawalPenaltyResult
│   ├── early_withdrawal_penalty.py     # NEW: compute_early_withdrawal_penalty(),
│   │                                    #      EARLY_WITHDRAWAL_PENALTY_RATE SourcedFigure
│   └── __init__.py                     # re-exports the two new symbols + the new function
├── comparison/
│   ├── models.py                # PlanYearProjection gains early_withdrawal_penalty;
│   │                             # PlanOutcome gains cumulative_early_withdrawal_penalty_paid
│   └── projection.py            # run_plan_projection() computes and funds the penalty each
│                                 # plan year; _derive_outcome() sums the new cumulative field
└── reporting/
    ├── models.py                 # summary type gains median_lifetime_early_withdrawal_penalty_paid
    ├── aggregation.py            # derives it from PlanOutcome, mirroring irmaa/niit exactly
    └── export.py                 # CSV column addition, mirroring irmaa/niit exactly

apps/streamlit_ui/src/rp_ui/
└── narration.py                  # + "Lifetime early-withdrawal penalty paid" entry, mirroring
                                   #   the existing IRMAA/NIIT entries exactly

docs/
└── BRD.md                        # §6.6 (or a new §6.6a) and §7 updated

tests/
├── unit/tax/test_early_withdrawal_penalty.py   # NEW: rate/base/exemption cases
├── unit/comparison/test_projection.py           # + penalty-in-a-real-projection cases,
│                                                 #   including the 019-flag combination
├── unit/reporting/test_aggregation.py           # + summary field derivation case
├── unit/reporting/test_export.py                # + CSV column case
└── apps/streamlit_ui/tests/unit/test_narration.py  # + new entry case
```

**Structure Decision**: Follows the existing package layout exactly, joined by the same
reporting/UI ripple `010` established for IRMAA/NIIT (the only prior feature to add a new
"lifetime X paid" figure) — this feature is closer in shape to that one than to `018`/`019`'s own
narrower, comparison-package-only scope. The new consumption function joins a new sibling module in
`tax/` (not `mechanics/`) since the 10% additional tax is itself a tax-liability concept (reported
on Form 5329, added to total tax owed), matching `niit.py`'s/`irmaa.py`'s own precedent rather than
`mechanics/withdrawal_sequencing.py`'s.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
