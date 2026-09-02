# Implementation Plan: Monte Carlo Per-Path Probabilistic Death Draws

**Branch**: `023-probabilistic-death-draws` | **Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/023-probabilistic-death-draws/spec.md`

## Summary

Fixes rp-vgv: every Monte Carlo path in `simulation/monte_carlo.py` currently runs against the
household's single, statically-configured `predicted_death_age` (if any) -- identical for every
path -- so a path's own `success_rate`/`percentile_bands` never reflect survivor-scenario risk; the
engine's only mortality-aware Monte Carlo output is the existing `survival_adjusted_success_rate`, a
post-hoc threshold check that never touches what a path actually funds. This feature adds a new,
opt-in capability: a caller pre-generates one death-age draw per household member per path (a new
`generate_death_age_draws()` in a new `simulation/mortality.py`, sampling each member's *conditional*
survival distribution given alive at their own current age -- a deliberate improvement over the older
metric's unconditional check), and passes the result into `run_simulation()`/`compare_*()` as a new
`death_year_draws` parameter, mirroring `return_paths`' own existing pre-generate-once-reuse-everywhere
shape exactly. Inside `monte_carlo.py`, each path's own draw replaces that path's `Household` copy's
`predicted_death_age` values (via `dataclasses.replace()`) immediately before its
`run_plan_projection()` call -- reusing 018's existing survivor-scenario mechanics (filing status,
survivor Social Security, spending reduction) completely unchanged, so no change to
`comparison/projection.py` is needed at all. Unused (the default), output is byte-for-byte identical
to today.

## Technical Context

**Language/Version**: Python 3.11+ (matches this project's existing constraint; no new dependency).

**Primary Dependencies**: None new -- stdlib `random`/`dataclasses` only, exactly like
`simulation/returns.py` and the rest of `simulation/monte_carlo.py` already use.

**Storage**: N/A -- in-memory dataclasses, same as every existing simulation-engine feature.

**Testing**: `pytest`. New `tests/unit/simulation/test_mortality.py` (draw conditioning, boundary
handling, reproducibility, distribution sanity -- SC-002/SC-003). Extended
`tests/unit/simulation/test_survival.py` (coexistence with `survival_adjusted_success_rate`, the new
eager-validation error cases). Extended `tests/unit/simulation/test_monte_carlo.py` (per-path
household override applied correctly, byte-identical when unused -- FR-007/SC-005, serial/parallel
dispatch parity -- SC-003). Extended `tests/unit/simulation/test_compare.py` (paired-draw reuse across
candidates -- SC-004). Extended `tests/integration/test_simulation_performance.py` (reference-scale
benchmark with this capability enabled -- FR-012/SC-006).

**Target Platform**: Same as the rest of this project -- a single-user, offline-first CLI/library
(constitution Principle V). No BFF/UI target for this feature (scope decision, spec.md Assumptions).

**Project Type**: Library feature (core `retirement_planner.simulation` subpackage only) -- not a new
deployable unit, no ripple into `services/bff` or `apps/streamlit_ui`.

**Performance Goals**: Reference-scale Monte Carlo run (3,000-5,000 paths) with this capability
enabled stays well under the constitution's one-minute budget (Principle VI) -- confirmed by a new
benchmark case (research.md §8), not assumed. Per-path added work is O(members) dict lookups plus a
handful of `dataclasses.replace()` calls; draw generation itself is O(path_count × members), each unit
a bounded scan over at most 61 documented ages.

**Constraints**: Must preserve reproducibility (Principle II) for both the new draw stream (its own
independent seed) and the pre-existing return-path stream (completely unperturbed by this feature,
research.md §5) -- same scenario + seed always reproduces identical draws and results, serial or
parallel dispatch. Must be a no-op (byte-for-byte identical output) for any caller that doesn't pass
`death_year_draws` (FR-007, SC-005) -- the overwhelming majority of existing callers and every
existing test.

**Scale/Scope**: One new module (`simulation/mortality.py`, ~2 functions). `monte_carlo.py` gains one
new `run_simulation()` parameter plus eager validation, one new private helper
(`_household_for_path()`), and a signature change to two existing private worker functions
(`_run_one_path()`, `_run_one_path_shared()`) to carry the per-path draw alongside the existing
per-path `ReturnPath`. `compare.py`'s four `compare_*()` functions each gain one passthrough
parameter (no new logic -- research.md §2). `simulation/__init__.py` exports the new function.
`docs/BRD.md`'s simulation-engine/mortality section is updated.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Accuracy Over Cleverness | The conditional-sampling design (research.md §4) and every boundary rule are explicitly documented in code and in `docs/BRD.md`, including where it deliberately diverges from the older, still-unchanged `survival_adjusted_success_rate` check's own unconditional imprecision (FR-002, FR-011) -- not silently absorbed. | PASS |
| II. Reproducibility | A single, independently-seeded, documented-order `random.Random` stream (research.md §5) -- same scenario/path-count/seed always reproduces identical draws and results, serial or parallel dispatch (FR-004, SC-003). The pre-existing return-path stream is untouched (research.md §5's rejected alternative). | PASS |
| III. Auditability | Every draw's underlying `SurvivalCurve` keeps its own real citation/`verified` metadata; `run_simulation()` requires `survival_curves` alongside `death_year_draws` specifically so the existing citation-attachment code path already covers this feature for free (research.md §3, FR-009) -- no new, unverified figure silently introduced. | PASS |
| IV. Extensibility Through Module Interfaces | New logic lives in a new module (`mortality.py`) plus `monte_carlo.py`/`compare.py`'s own existing extension points; `comparison/projection.py`'s already-locked, spec-owned (018) contract is untouched (research.md §6, FR-006). | PASS |
| V. Offline-First | No network dependency introduced. | PASS |
| VI. Performance Budget | Reference-scale run confirmed well under budget by a new benchmark case, not assumed (research.md §8, FR-012, SC-006). | PASS |
| Paired-draw comparison standard | `death_year_draws`, once generated, is passed unchanged into every comparison candidate's own `run_simulation()` call -- structurally identical to how `return_paths` already satisfies this standard (research.md §2, FR-005, SC-004). | PASS |
| Config as data, not code | This feature adds no new scenario-config field -- `death_year_draws` is a caller-side, pre-generated Python value passed programmatically (exactly like `return_paths`), not a YAML input. | PASS |

No violations -- Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/023-probabilistic-death-draws/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── simulation-api.md   # addendum to 005-simulation-engine
└── tasks.md             # Phase 2 output (/speckit-tasks -- not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/simulation/
├── mortality.py            # NEW -- generate_death_age_draws(), _draw_death_age()
├── monte_carlo.py          # run_simulation() gains death_year_draws param + eager validation;
│                            # _run_one_path()/_run_one_path_shared() carry the per-path draw;
│                            # new _household_for_path() helper
├── compare.py               # compare_states()/compare_roth_conversion_strategies()/
│                            # compare_withdrawal_sequencing_strategies()/compare_claiming_age_grid()
│                            # each gain one passthrough death_year_draws parameter
└── __init__.py               # exports generate_death_age_draws

docs/
└── BRD.md                  # simulation-engine / mortality section updated (data-model.md)

tests/unit/simulation/
├── test_mortality.py         # NEW -- draw conditioning, boundaries, reproducibility, distribution
├── test_survival.py          # + coexistence and eager-validation-error cases
├── test_monte_carlo.py       # + per-path override, byte-identical-when-unused, dispatch parity
└── test_compare.py           # + paired-draw reuse across candidates

tests/integration/
└── test_simulation_performance.py   # + reference-scale benchmark with this capability enabled
```

**Structure Decision**: Follows the existing package layout exactly -- no new top-level package, no
new deployable unit. The one new module (`mortality.py`) mirrors `returns.py`'s existing role
(seeded, per-path generation logic, separate from pure data) rather than being folded into
`survival_data.py` (data only) or `monte_carlo.py` (orchestration only) -- research.md §1.

## Complexity Tracking

*No Constitution Check violations -- this section is intentionally empty.*
