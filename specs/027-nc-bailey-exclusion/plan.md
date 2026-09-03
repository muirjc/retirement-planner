# Implementation Plan: Source-Attributed Retirement Income for State Exclusions (NC Bailey Settlement)

**Branch**: `027-nc-bailey-exclusion` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-nc-bailey-exclusion/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

024-nc-state-tax deliberately left the Bailey settlement unmodeled because `IncomeComponents`
carries only one blended `ordinary_income` figure with no per-source breakdown. This feature adds
a household-attested `bailey_qualifying` flag to `IncomeStream` (scenario layer), sums flagged
streams' amounts into a new, additive `government_pension_income` field on `IncomeComponents` (tax
layer, populated by `comparison/projection.py`), and has `tax/state/nc.py` exclude that amount from
NC's taxable base while every other consumer of `ordinary_income` (federal tax, FICA, IRMAA, NIIT)
and every other state module (SC/DE/FL) is untouched — matching 024's research.md §3 option (1).

## Technical Context

**Language/Version**: Python 3.11+ (existing project convention, constitution Technology & Architecture Constraints)

**Primary Dependencies**: None new — reuses existing `dataclasses`, `pytest`; no third-party addition

**Storage**: Scenario YAML files (existing `scenario/loader.py` / `scenario/store.py` round-trip), N/A otherwise

**Testing**: `pytest tests/` (core library) — this feature touches only `src/retirement_planner/{scenario,tax,comparison}` and their existing test trees under `tests/`

**Target Platform**: Same as the rest of the core library — offline, no network dependency (constitution Principle V)

**Project Type**: Single Python library project (existing `src/retirement_planner/` layout) — no BFF, UI, or simulation-layer change (spec.md scope boundary; simulation calls `comparison.run_plan_projection()` unchanged)

**Performance Goals**: No new computation of consequence — one boolean-filtered sum over each member's already-iterated `income_streams` per plan year, well within the existing Monte Carlo performance budget (constitution Principle VI)

**Constraints**: Additive-only: every existing scenario YAML, and every non-NC state module's output, MUST be byte-for-byte unchanged (spec.md FR-002, FR-006, FR-007)

**Scale/Scope**: One new dataclass field on `IncomeStream`, one new dataclass field on `IncomeComponents`, one new private helper in `comparison/projection.py`, one modified `compute_tax()` in `tax/state/nc.py`; no new module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness**: PASS. The Bailey exclusion is either applied in full (household-attested, source-and-vesting-date-qualifying income) or not at all — no partial/approximate modeling is introduced. The gap this closes (024's honestly-documented omission) is being closed accurately, not papered over. The module docstring continues documenting what is and isn't modeled (the separate S.L. 2021-180 military exemption remains out of scope, documented as such).
- **II. Reproducibility**: PASS. `bailey_qualifying` is a static, user-configured boolean; no randomness, no new seed-dependent path.
- **III. Auditability**: PASS with a documented distinction (mirrors NC's own existing "Social Security is never read, not a SourcedFigure" precedent): the Bailey rule is a categorical (100%-or-nothing) legal exemption with no rate or dollar figure to schedule by tax year, so it is documented as a structural rule with an inline citation (N.C. Gen. Stat. §105-134.6 history; *Bailey v. State of North Carolina*, 1998) in `nc.py`'s docstring and test module, not a new `SourcedFigure` — consistent with how this module already treats NC's Social-Security-is-untaxed fact. No numeric figure changes; NC's existing `_NC_FLAT_RATE` `SourcedFigure` is untouched.
- **IV. Extensibility Through Module Interfaces**: PASS. `IncomeComponents` gains one additive, defaulted field; `compute_state_tax()`'s dispatch and every other state module's `compute_tax()` signature are unchanged. SC/DE/FL simply never read the new field (same "accepts the whole `IncomeComponents`, reads only what it needs" shape they already have).
- **V. Offline-First**: PASS. No new external data source; the flag is scenario-config-supplied, matching every other household attestation (`ss_claim_age`, `hdhp_coverage`, ...).
- **VI. Performance Budget**: PASS. A single filtered sum per plan year over an already-bounded `income_streams` list adds no meaningful cost to the existing Monte Carlo loop.
- **Verified-figure gate**: N/A — no new `SourcedFigure` is introduced (see Auditability above); NC's existing verified flat-rate figure is unchanged.
- **Unit test coverage for numeric primitives**: `tax/state/test_nc.py` gets new cases for the Bailey exclusion (full exclusion, partial exclusion, floor at $0, unaffected-when-unset) before this feature is used in any comparative run.

No violations — Complexity Tracking is not needed.

**Post-Phase 1 re-check**: research.md and data-model.md confirm the design stayed exactly within
what this gate anticipated — one additive `IncomeStream` field, one additive `IncomeComponents`
field, one new private projection helper, one modified `nc.py` calculation, no new `SourcedFigure`.
Gate still PASSES with no changes.

## Project Structure

### Documentation (this feature)

```text
specs/027-nc-bailey-exclusion/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── scenario-api.md  # addendum: IncomeStream.bailey_qualifying
│   ├── tax-api.md       # addendum: IncomeComponents.government_pension_income, nc.py behavior
│   └── comparison-api.md # addendum: new private helper + IncomeComponents construction
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/retirement_planner/
├── scenario/
│   ├── models.py      # IncomeStream gains bailey_qualifying: bool = False
│   ├── loader.py       # _build_income_stream reads optional "bailey_qualifying"
│   └── store.py        # _income_stream_to_dict round-trips bailey_qualifying
├── tax/
│   ├── models.py        # IncomeComponents gains government_pension_income: float = 0.0
│   └── state/
│       └── nc.py         # compute_tax() excludes government_pension_income from taxable base
└── comparison/
    └── projection.py     # new helper sums Bailey-qualifying stream income; passed into IncomeComponents

tests/
├── scenario/            # loader/store round-trip coverage for the new field
├── tax/state/
│   └── test_nc.py        # Bailey exclusion unit tests
└── comparison/           # projection-level test: federal/FICA/IRMAA/NIIT unaffected, NC reduced, SC/DE/FL unaffected

docs/BRD.md               # §5.4 NC row updated
```

**Structure Decision**: Single existing Python library project (`src/retirement_planner/`). No new
top-level package — this feature extends three existing subpackages (`scenario`, `tax`,
`comparison`) along already-established seams (additive dataclass fields, one new private
projection helper, one modified state module), matching 021-pension-annuity-income's own precedent
for adding a household-level income concept without touching the simulation/BFF/UI layers.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
