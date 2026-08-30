# Implementation Plan: Figure Verification (Placeholder Tax Figures)

**Branch**: `014-figure-verification` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-figure-verification/spec.md`

## Summary

Corrects the citation, `last_verified` date, and `verified` flag on the 8
`SourcedFigure` instances a real run (scenario B) surfaced still shipping
`verified=False`, across 6 existing files: `tax/niit.py` (`niit_rate`,
`niit_threshold_mfj`/`_single`) and `tax/social_security.py`
(`ss_provisional_income_thresholds_mfj`/`_single`) need only re-citation —
their fixed-by-statute dollar figures are already numerically correct;
`tax/federal.py` (`federal_brackets_mfj`/`_single`), `tax/irmaa.py`
(`irmaa_tiers_mfj`/`_single`), and `mechanics/hsa.py`
(`hsa_contribution_limits`) need their round-number placeholder dollar
figures replaced with a specific, named real tax year's actual published
figures, per the "flat real-dollar schedule" convention `federal.py`'s own
docstring already establishes and `irmaa.py`/`hsa.py` explicitly reuse;
`mechanics/rmd.py` needs two changes — `uniform_lifetime_table`'s existing
divisors cross-checked and corrected (mirroring `rp-6c5`'s precedent, where
a sibling table's placeholder values were measurably wrong), with coverage
extended from ages 72-100 to the full IRS Pub. 590-B Table III range, and
`rmd_start_age`'s single flat `SourcedFigure[int]` schedule replaced with a
two-part schedule (73 before 2033, 75 from 2033 on) reflecting SECURE 2.0's
already-known future step, keyed by tax year rather than the account
owner's birth-year cohort (spec.md Assumptions). No public function
signature, data model shape, or API contract changes — every one of the 6
functions that consume these figures (`compute_federal_tax`,
`compute_irmaa_surcharge`, `compute_niit`, `compute_taxable_social_security`,
`compute_hsa_eligibility`, `compute_rmd`) keeps its existing locked
signature from `002`/`003`/`010`'s contracts untouched.

## Technical Context

**Language/Version**: Python 3.11+ — same project, same interpreter floor
as `001`–`013` (`pyproject.toml` still pins `>=3.11`).

**Primary Dependencies**: No new third-party runtime dependency. This
feature's only in-repo touchpoints are `retirement_planner.tax` (`niit.py`,
`social_security.py`, `federal.py`, `irmaa.py`) and
`retirement_planner.mechanics` (`hsa.py`, `rmd.py`) — all existing modules,
no new module. `SourcedFigure` itself (`tax/models.py`, `002`'s data model)
is unchanged; this feature only edits *instances* of it.

**Storage**: None new. `SourcedFigure` schedules are Python literals in
source, not persisted data — same as every figure `002`–`013` already
ship.

**Testing**: pytest, continuing `001`–`013`'s convention — each touched
module already has a `tests/unit/tax/test_*.py` or
`tests/unit/mechanics/test_*.py` sibling with at least one test asserting
`verified is False` today (following `rp-6c5`'s precedent in
`test_inherited_rmd.py`, this feature flips each to a
`verified is True` + spot-check-against-source assertion).

**Target Platform**: Same as `001`–`013`: local developer/user machine,
offline. No network access at runtime — the primary-source lookups this
feature depends on (Rev. Proc. PDFs, CMS.gov tables, statute text, IRS
Pub. 590-B) happen once, during implementation research, and their
findings are baked into source as literals and citations; nothing this
feature adds performs a lookup at run time (Constitution Principle V).

**Project Type**: Continues the existing three-package layout
(`src/retirement_planner`, `services/bff`, `apps/streamlit_ui`) with no new
package, subpackage, module, or file. `services/bff` and
`apps/streamlit_ui` are untouched — neither exposes per-figure citation
detail today, and this feature doesn't change that.

**Performance Goals**: No change. Every touched function is still one
dict/tuple lookup per call; `rmd_start_age`'s schedule changes from one
range comprehension to two, still a `dict[int, int]` built once at import
time, not a per-call cost.

**Constraints**: A projection using any of these 6 files for a tax year
already covered by `_DOCUMENTED_YEARS` (2020-2074) must keep working
exactly as before for every year where the corrected value equals the old
placeholder (no behavior change) and must produce the *correct* computed
output for every year where it doesn't (the entire point of Group B/C
corrections — spec.md Edge Cases explicitly calls this an intended
consequence, not a regression). Because `rmd_start_age` and
`uniform_lifetime_table` are load-bearing for RMD amounts, and existing
tests (`test_projection.py`, `test_compare.py`, `test_monte_carlo.py`) run
scenarios spanning years past 2033, any test that hardcodes an expected RMD
amount for a member turning the start age in 2033 or later, or for a member
aged over 100, may need its expected value updated to match the corrected
figure — this is a required, reviewed part of the change, not a fixture to
route around.

**Scale/Scope**: 8 figures, 6 files, 0 new files. Two figures
(`rmd_start_age`, `uniform_lifetime_table`) change their underlying
schedule/table shape; the other 6 change only citation/`verified` metadata
(and, for Group B, the dollar/rate literals a citation points at).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Accuracy Over Cleverness** — ✅ PASS. This feature exists *because*
  of this principle — closing exactly the gap it describes (a figure
  presented as settled must not actually be an unconfirmed placeholder).
  The one still-undisclosed simplification this feature introduces
  (`rmd_start_age` modeled as a tax-year step, not the law's actual
  birth-year cohort rule) is explicitly documented in the module docstring
  and named as a known simplification in spec.md's Assumptions, not
  silently absorbed — same treatment `federal.py`'s "real dollars, no
  indexing engine" simplification already gets today.
- **II. Reproducibility** — ✅ PASS. Every changed figure is still a pure
  literal schedule; no randomness, no I/O at call time. Same scenario +
  same seed still produces identical output (the *values* may differ from
  before this feature ships, which is intended — see Constraints above —
  but re-running after the change is deterministic).
- **III. Auditability** — ✅ PASS. This is the Auditability gate's own
  enforcement mechanism at work: every one of the 8 figures gets a citation
  naming a specific source document/section/page and `verified=True`,
  replacing "placeholder — pending verification" text (Principle III's own
  requirement).
- **IV. Extensibility Through Module Interfaces** — ✅ PASS. No interface
  changes. Each figure stays inside the module that already owns it; no
  new extension point needed since this feature adds no new *kind* of
  figure, only corrects existing ones.
- **V. Offline-First, No Runtime Network Dependency** — ✅ PASS. All
  primary-source lookups happen during implementation, not at run time
  (Technical Context, Target Platform above) — consistent with how
  `federal.py`'s and `irmaa.py`'s figures already work today, unverified
  or not.
- **VI. Performance Budget** — ✅ PASS. No new calls, no heavier lookups —
  see Performance Goals above.

**Technology & Architecture Constraints:**

- *"Config as data, not code"* — N/A; these figures aren't scenario input,
  they're the engine's own tax-law reference data, same category as every
  other `SourcedFigure` today.
- *Paired-draw comparison is the standard pattern* — Unaffected; this
  feature changes no comparison logic, only the figures comparisons read.
- *Scope boundary with the working document* — N/A, not implicated.

**Development Workflow & Quality Gates:**

- *Regression baseline* — Required, with the explicit exception noted in
  Constraints: reference scenarios/fixtures must produce identical output
  wherever the corrected figure equals the old placeholder, and
  *corrected* output wherever it doesn't — the diff must be traceable to
  a specific figure correction (spec.md SC-005), not incidental drift.
- *Verified-figure gate* — This feature's entire purpose: no figure may be
  marked `verified=True` without being cross-checked against a primary
  source first (constitution's own Development Workflow gate, restated by
  this feature's every functional requirement).
- *Unit test coverage for numeric primitives* — Required: each figure gets
  (or has extended) a test pinning `verified is True` and spot-checking
  the actual values against the cited source, following
  `test_inherited_rmd.py`'s
  `test_single_life_expectancy_table_is_verified_and_covers_every_published_age`
  precedent from `rp-6c5`.

**Post-Phase 1 re-check**: Confirmed after generating research.md and
data-model.md — no new violations. No `contracts/` artifact is generated
(Phase 1, step 2) because this feature changes no public function
signature or request/response shape; the existing locked contracts in
`002-tax-calculation-engine/contracts/tax-api.md`,
`003-retirement-account-mechanics/contracts/mechanics-api.md`, and
`010-advanced-tax-benefits/contracts/{tax-api,mechanics-api}.md` already
describe every function this feature touches and remain accurate as-is.

## Project Structure

### Documentation (this feature)

```text
specs/014-figure-verification/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory — see Constitution Check's Post-Phase 1 re-check.

### Source Code (repository root)

```text
src/retirement_planner/
├── tax/
│   ├── niit.py               # _NIIT_THRESHOLDS, _NIIT_RATE: citation + verified=True (Group A)
│   ├── social_security.py    # _THRESHOLDS: citation + verified=True (Group A)
│   ├── federal.py            # _MFJ_BRACKETS/_SINGLE_BRACKETS literals corrected to a named
│   │                          # Rev. Proc. year; _FEDERAL_BRACKETS: citation + verified=True (Group B)
│   └── irmaa.py               # _MFJ_TIERS/_SINGLE_TIERS literals corrected to a named CMS.gov
│                               # year; _IRMAA_TIERS: citation + verified=True (Group B)
└── mechanics/
    ├── hsa.py                 # _HSA_LIMITS literal corrected/confirmed against a named Rev. Proc.
    │                           # year; citation + verified=True (Group B)
    └── rmd.py                  # _UNIFORM_LIFETIME_DIVISORS: corrected + extended to full IRS
                                 # Pub. 590-B Table III age range; UNIFORM_LIFETIME_TABLE: citation
                                 # + verified=True (Group C). RMD_START_AGE.schedule: split into a
                                 # pre-2033 (73) / 2033-on (75) two-part schedule; citation +
                                 # verified=True (Group C)

tests/unit/
├── tax/
│   ├── test_niit.py             # verified is True assertion + statute spot-check
│   ├── test_social_security.py  # verified is True assertion + statute spot-check
│   ├── test_federal.py          # verified is True assertion + Rev. Proc. spot-check;
│   │                             # update any hardcoded-bracket expected-tax fixture the
│   │                             # correction shifts
│   └── test_irmaa.py            # verified is True assertion + CMS.gov spot-check;
│                                 # update any hardcoded-tier expected-surcharge fixture
├── mechanics/
│   ├── test_hsa.py               # verified is True assertion + Rev. Proc. spot-check
│   └── test_rmd.py                # verified is True (both figures) + IRS Pub. 590-B divisor
│                                   # spot-checks across the extended age range; +2033-straddle
│                                   # start-age case (member turning 73 in 2032 vs. 2033)
└── comparison/
    ├── test_projection.py        # update any fixture whose expected RMD/tax/surcharge amount
    │                               # shifts because a corrected figure changed it (traceable per
    │                               # spec.md SC-005 — see Constraints above)
    └── test_compare.py           # same, for comparison-layer fixtures
```

**Structure Decision**: Continues `001`–`013`'s existing package layout
with zero new files anywhere — every path above already exists. This is
the narrowest possible structural footprint: 6 source files get literal
and metadata corrections, their existing sibling test files get extended
(never replaced), and any downstream test whose fixture value shifts as an
intended consequence gets its expected value updated in place. No new
entity, module, contract, or UI surface is introduced (data-model.md
confirms `SourcedFigure` itself is unchanged).

## Complexity Tracking

*No constitution violations were found (see Constitution Check above) —
this section is not needed.*
