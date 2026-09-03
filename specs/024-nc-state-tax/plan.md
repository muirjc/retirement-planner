# Implementation Plan: North Carolina State Income Tax Module

**Branch**: `024-nc-state-tax` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/024-nc-state-tax/spec.md`

## Summary

Adds `tax/state/nc.py` — a new leaf state-tax module, structurally modeled on `tax/state/sc.py` (a `SourcedFigure`-backed `BracketRow` table run through the existing `apply_progressive_brackets()`), but with exactly one bracket row per tax year (`income_up_to=None`) since North Carolina has been a true flat-rate state (no thresholds at all) since 2014. Two tax years are legislated and confirmed against NCDOR's primary source: 4.25% for tax year 2025, 3.99% for tax year 2026 onward (N.C. Gen. Stat. §105-153.7, as amended by S.L. 2023-134) — the 3.99% figure is held flat through the rest of the module's documented horizon, matching every other module's existing convention. Unlike SC's/DE's age-based exclusion, NC introduces **no** exclusion `SourcedFigure`: North Carolina's only comparable mechanism (the Bailey settlement) is scoped by income source and pre-8/12/1989 pension vesting date, which `IncomeComponents` cannot represent without a `comparison/`/`simulation/`-level change this feature is explicitly not making (spec.md Assumptions). `STATE_MODULES` gains one `"NC": nc.compute_tax` entry. `docs/BRD.md` §2.3 and §5.4 move NC from the not-yet-implemented candidate list into the implemented table.

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard)

**Primary Dependencies**: none new — reuses `tax/bracket_math.py`'s existing `apply_progressive_brackets()` and `tax/models.py`'s existing `BracketRow`, `SourcedFigure`, `StateTaxResult`

**Storage**: N/A — no new scenario-configuration input; NC is selected the same way `"SC"`/`"DE"`/`"FL"` already are (an existing `state` config field)

**Testing**: `pytest tests/` (core — new `tax/state/test_nc.py`, extends `dependency_containment`/any other `STATE_MODULES`-parametrized test), `pytest services/bff/tests/` (confirms the reference/dropdown route picks up `"NC"` with no route code change)

**Target Platform**: Linux/macOS dev laptop, offline (constitution Principle V)

**Performance Goals**: No material change — one more `dict` lookup + one more `apply_progressive_brackets()` call over a one-row table, negligible

**Constraints**: Must not alter `compute_state_tax()`'s own signature or logic, or any existing state module's behavior; must reproduce every existing scenario's output exactly for `"SC"`/`"DE"`/`"FL"`; NC's flat rate MUST ship `verified=True` (cross-checked against NCDOR's Tax Rate Schedules page and N.C. Gen. Stat. §105-153.7 during this feature's research — constitution Principle III's verified-figure gate), unlike SC's/DE's inherited `verified=False` placeholders

**Scale/Scope**: `tax/state/` only (new `nc.py` + one `STATE_MODULES` registry line + one new `test_nc.py`) plus `docs/BRD.md` §2.3/§5.4. No `comparison/`, `simulation/`, BFF, or UI code changes — the BFF's `reference.py` route and the Streamlit state dropdown are both already state-agnostic (`STATE_MODULES`-key-driven) and need only be *confirmed*, not changed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness**: PASS. The one deliberate simplification (no Bailey-settlement modeling) is explicitly documented in spec.md's Assumptions and will be restated in the `nc.py` module docstring and `docs/BRD.md` §5.4, not silently absorbed into the tax result.
- **II. Reproducibility**: PASS. `compute_tax()` is a pure function of `(income, filer_ages, filing_status, tax_year)` — no randomness, no I/O.
- **III. Auditability**: PASS, and stronger than SC's/DE's precedent — the flat-rate `SourcedFigure` carries a real citation (N.C. Gen. Stat. §105-153.7, as amended by S.L. 2023-134) confirmed against NCDOR's official Tax Rate Schedules page during this feature's own research, shipped `verified=True` rather than as inherited placeholder debt.
- **IV. Extensibility Through Module Interfaces**: PASS. One new module (`tax/state/nc.py`) + one new `STATE_MODULES` entry; `compute_state_tax()` itself is untouched — exactly the extension shape Principle IV describes.
- **V. Offline-First**: PASS. Hardcoded `SourcedFigure` schedule, no runtime lookup; the NCDOR research happened during planning, not at run time.
- **VI. Performance Budget**: PASS. Negligible — one more dict-keyed state module identical in cost shape to SC/DE/FL's existing ones.

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/024-nc-state-tax/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output (addendum to 002's tax-api.md)
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
src/retirement_planner/
└── tax/
    └── state/
        ├── nc.py           # NEW: _NC_FLAT_RATE (SourcedFigure of one-row BracketRow tables,
        │                   #      keyed by tax year) + compute_tax(); no exclusion SourcedFigure
        ├── __init__.py     # + `nc` import, + "NC": nc.compute_tax in STATE_MODULES
        └── test_nc.py      # NEW: zero-income floor, representative middle-income case (both
                             #      documented rates), high-income (no cap/cliff), unsupported-
                             #      tax-year error, Social-Security-not-taxed case

docs/BRD.md                 # §2.3: move NC out of the not-yet-implemented parenthetical list
                             # §5.4: new table row (structure + verification status), heading
                             #       renamed to include North Carolina
```

**Structure Decision**: Extends only the existing leaf `tax/state/` package, mirroring `sc.py`'s own file shape almost exactly (see Summary) — the smallest and most directly comparable precedent, since NC is "one more state module" in the same sense SC/DE/FL already are. No `comparison/`, `simulation/`, BFF, or Streamlit source changes (Technical Context) — only `services/bff/tests/` and `apps/streamlit_ui/tests/`-level *confirmation* that the state-agnostic plumbing already picks NC up, per spec.md FR-008/SC-004.
