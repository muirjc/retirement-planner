# Implementation Plan: Federal & State Tax Calculation Engine

**Branch**: `002-tax-calculation-engine` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-tax-calculation-engine/spec.md`

## Summary

A pure, offline tax calculator: given a household's filing status, filer ages, ordinary income, Social Security gross benefit, state of residence, and a tax year, compute federal tax (genuine progressive brackets + real 0%/50%/85% Social Security provisional-income taxability) and state tax (via an independent, pluggable module per state — real bracket-by-bracket math for South Carolina and Delaware, a trivial zero-tax module for Florida). Every rate, bracket edge, and exclusion amount used is individually traceable to a citation, a last-verified date, and a confirmed/needs-verification status; figures that change by law over time are modeled as an explicit year→value schedule, and a tax year outside a figure's documented schedule is refused (with a clear error identifying the figure and year) rather than extrapolated. This is a downstream-consumer library, like `001-scenario-config-management`: no CLI, no wiring to `Scenario`, no IRMAA/NIIT, no account-withdrawal logic.

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor as `001-scenario-config-management` (`pyproject.toml` already pins `>=3.11`).

**Primary Dependencies**: Standard library only (`dataclasses`, `typing`). No new runtime dependency is needed — tax computation is pure arithmetic over Python-native data structures; there is no file parsing, network call, or numeric library requirement in this feature (unlike `001`, which needed PyYAML for user-authored config files — tax rule tables here are *code*, not user data; see research.md §2 for why).

**Storage**: None. Tax rule tables (federal brackets, each state's brackets/exclusions, each figure's citation/date/schedule) are Python module-level constants, loaded once at import time — not files read at call time, not a database.

**Testing**: pytest — continuing `001`'s convention.

**Target Platform**: Same as `001`: local developer/user machine, offline, invoked as a library.

**Project Type**: Single Python library project (`src/` layout) — continuing `001`'s structure, adding a sibling `tax` subpackage alongside `scenario`.

**Performance Goals**: A single federal-or-state tax computation should complete in well under 10ms — this is arithmetic over a handful of bracket rows, not I/O. This matters beyond this feature alone: the future simulation engine (§3.5, not yet spec'd) will call this engine once per simulated year per path (potentially 5,000 paths × ~35 years × multiple states), so the design must not reload or re-parse rule tables per call — they're loaded once at import time (see Constraints).

**Constraints**: No network access at any point (FR-014); every figure's citation/date/verification-status/schedule MUST be inline with the figure itself, not a separate lookup step, so a result can report its own provenance without a second query; rule tables MUST be loaded once at module import, not per call, to keep the future high-volume simulation use case fast.

**Scale/Scope**: This feature's own direct scope is one household/one tax year per call. Designed so the future simulation engine can call it at high volume (thousands of paths × decades × states) without this feature's design becoming the bottleneck.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution (v1.0.0, ratified 2026-08-27) is now active — unlike `001`, which was planned before ratification. Evaluated against all six principles plus the Technology/Architecture Constraints and Development Workflow gates:

- **I. Accuracy Over Cleverness** — ✅ PASS. This feature's documented simplifications (ordinary-income-only scope, IRMAA/NIIT deferral, SC/DE/FL-only module coverage) are recorded in spec.md's Assumptions and FR-017, and every computed result surfaces which figures are unverified (FR-009–FR-011) rather than hiding the gap.
- **II. Reproducibility** — ✅ PASS (trivially). No randomness is involved; the same inputs and tax year always produce the same result.
- **III. Auditability** — ✅ PASS. This is the feature's central design driver: every figure carries a citation, last-verified date, and verification status (FR-009), individually traceable from any result (FR-010), and an unverified figure is never indistinguishable from a verified one (FR-011).
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. FR-005 and SC-006 require every state module to be independent and pluggable; the federal calculation and other states' modules must not change when a new state is added.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. FR-014 states this directly; rule tables are in-process constants.
- **VI. Performance Budget** — ✅ PASS (not directly exercised yet). This feature's own computations are trivial; see Performance Goals above for why the design still guards the future high-volume use case.

**Technology & Architecture Constraints — one interpretation worth recording explicitly:**

- *"Config as data, not code"* (constitution, Technology & Architecture Constraints) says scenario inputs must live in YAML, never hardcoded into engine code, "so changing a number MUST NOT require a code change." Tax rate/bracket/exclusion figures are **not** scenario inputs — they're facts about law, and Principle III (Auditability) requires each one to carry a citation and last-verified date and to go through the same review as the code that uses it. Storing them as user-editable YAML would let a figure change with no citation and no review, undermining Auditability to satisfy a constraint aimed at a different category of data. This plan therefore keeps tax rule tables as version-controlled Python module constants (data-shaped, but code-reviewed), consistent with the source requirement document's own architecture sketch (§5, `config/federal_tax_rules.py` and `config/state_tax_rules/*.py` are `.py` files, not `.yaml`). Scenario inputs (`001`'s domain) remain YAML; tax reference data (this feature's domain) does not. No violation — a scoping clarification, recorded here for any future contributor or `/speckit-analyze` pass.
- *Paired-draw comparison is the standard pattern* — N/A. This feature has no Monte Carlo or comparative-run logic; it's a deterministic calculator the future simulation engine will call.

**Development Workflow & Quality Gates:**

- *Regression baseline* — N/A in the "don't change existing output" sense: this feature is an intentional accuracy fix over the prototype's flat-85% Social Security shortcut and blended-rate state tax approximation (source doc §3.2 flags both as known gaps). Its numbers are *expected* to differ from the old prototype; Principle I favors that over preserving a known-wrong approximation.
- *Verified-figure gate* — Every figure shipped with this feature (SC, DE, FL, and federal brackets/thresholds) starts marked `needs verification` unless it is actually cross-checked against a primary source during implementation (IRS Rev. Proc. for federal brackets/SS thresholds; each state's Department of Revenue publication) — no figure is marked `verified` by default just because a number was typed in.
- *Unit test coverage for numeric primitives* — Required: federal bracket math against published 2026 MFJ thresholds, and each of SC/DE/FL's module against at least one hand-calculated example (source doc §7; this feature's SC-001/SC-002).

**Post-Phase 1 re-check**: Confirmed after generating research.md, data-model.md, contracts/tax-api.md, and quickstart.md — no new violations. `SourcedFigure` (data-model.md) makes citation/last-verified/verified mandatory on every figure (Principle III), `STATE_MODULES` (contracts/tax-api.md) keeps state modules independent and pluggable (Principle IV), and quickstart.md explicitly labels every illustrative figure as an unverified placeholder rather than presenting it as settled (Principle I).

## Project Structure

### Documentation (this feature)

```text
specs/002-tax-calculation-engine/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── tax-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── retirement_planner/
    ├── __init__.py
    ├── scenario/                     # 001-scenario-config-management (unchanged)
    │   └── ...
    └── tax/
        ├── __init__.py
        ├── models.py                 # IncomeComponents, FilerAges, FilingStatus, TaxYear,
        │                             # SourcedFigure (year→value schedule + citation/date/verified),
        │                             # FigureUsage, FederalTaxResult, StateTaxResult,
        │                             # UnsupportedTaxYearError
        ├── social_security.py         # compute_taxable_social_security(...) — provisional-income
        │                             # formula (FR-002); engine/social_security.py in the source
        │                             # doc's sketch
        ├── federal.py                  # compute_federal_tax(...) — bracket math + calls
        │                             # social_security.py; federal_tax_rules data lives here too
        └── state/
            ├── __init__.py             # STATE_MODULES registry: state code -> compute function (FR-005)
            ├── sc.py                    # South Carolina: real bracket-by-bracket (FR-006)
            ├── de.py                    # Delaware: real bracket-by-bracket (FR-006)
            └── fl.py                    # Florida: zero-tax reference module (FR-007)

tests/
├── unit/
│   └── tax/
│       ├── test_social_security.py     # provisional-income thresholds (US1)
│       ├── test_federal.py              # bracket math + SS integration (US1)
│       ├── test_state_sc.py              # SC bracket math (US2)
│       ├── test_state_de.py               # DE bracket math (US2)
│       ├── test_state_fl.py                # FL zero-tax (US2)
│       └── test_figure_tracking.py          # citation/verification/schedule behavior (US3)
└── integration/
    └── test_tax_lifecycle.py                # federal + state, multi-year schedule, quickstart.md walkthrough
```

**Structure Decision**: Continues `001`'s single Python library, `src/` layout — `tax/` is a sibling subpackage to `scenario/` inside the same `retirement_planner` package, independently importable (`import retirement_planner.tax`) with zero dependency on `scenario/` (per the spec's Assumptions: this feature takes income components directly, not a `Scenario`). State rule modules live inside the package (`retirement_planner/tax/state/`), not under top-level `config/`, despite the source document's architecture sketch showing `config/state_tax_rules/*.py` — see the Constitution Check note above for why: `001` already established `config/` as YAML-only user data, and tax rule tables are code-reviewed reference data, not user input, so they belong in the installable package like any other source module.

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) — this section is not needed.*
