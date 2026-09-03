# Feature Specification: North Carolina State Income Tax Module

**Feature Branch**: `024-nc-state-tax`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Add a North Carolina (NC) state income tax module to the retirement planner, following the same pattern as the existing SC and DE state tax modules. NC is the next candidate state per docs/BRD.md §2.3's reference use case (9 candidate states; only SC, DE, FL implemented today). Scope: research North Carolina's actual current individual income tax law (NC has been a flat-rate state since 2014, with the rate legislated to step down across tax years -- confirm the current schedule from N.C. Dept. of Revenue / N.C. Gen. Stat. Ch. 105) and any retirement-income exclusion analogous to SC's/DE's age-65 exclusion (note: NC's Bailey settlement grandfathers only pre-8/12/1989 state/local/federal government retirees -- this is NOT a general age-65 exclusion, so do not assume that shape applies). Implement tax/state/nc.py with compute_tax(income, filer_ages, filing_status, tax_year) -> StateTaxResult matching the locked compute_state_tax() interface, reuse apply_progressive_brackets() unless research shows it can't express NC's actual law, and register NC in STATE_MODULES. Every figure ships as a SourcedFigure with a real citation and last_verified date. No changes to comparison/, simulation/, the BFF, or the UI beyond confirming the existing state-agnostic reference/dropdown plumbing picks up the new STATE_MODULES entry. Update docs/BRD.md §5.4 and §2.3. Add tax/state/test_nc.py."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evaluate North Carolina as a candidate retirement state (Priority: P1)

A household comparing candidate retirement states (per the tool's reference use case, `docs/BRD.md` §2.3) wants to add North Carolina to the comparison and get a tax result computed against NC's real, current flat-rate tax law, not a placeholder or an unsupported-state error.

**Why this priority**: This is the entire reason the issue exists — NC is the next named candidate state without a real module, and a household cannot evaluate it today.

**Independent Test**: Configure a household with state `"NC"` and a representative ordinary income, run a projection for a documented tax year, and confirm the state tax owed equals that income times NC's statutory flat rate for that year, with no error.

**Acceptance Scenarios**:

1. **Given** a household with $80,000 of ordinary income and tax year 2026, **When** NC state tax is computed, **Then** the result is `80,000 * 3.99%` = $3,192.00 (North Carolina's flat rate for tax year 2026 and later, N.C. Gen. Stat. §105-153.7 as amended by S.L. 2023-134).
2. **Given** the same household and tax year 2025, **When** NC state tax is computed, **Then** the result is `80,000 * 4.25%` = $3,400.00 (the legislated 2025 rate, one year ahead of the 2026 step-down).
3. **Given** a household with $0 ordinary income, **When** NC state tax is computed for any documented tax year, **Then** the result is $0.00 (no negative tax, matching SC/DE/FL's existing floor behavior).

---

### User Story 2 - Social Security income stays untaxed when comparing against NC (Priority: P2)

A household comparing states that already trusts the tool's SC/DE modeling (Social Security not taxed by the state) wants North Carolina held to the same accurate treatment — NC also does not tax Social Security benefits — so cross-state comparisons stay apples-to-apples.

**Why this priority**: Without this, NC would either wrongly tax Social Security (overstating its cost relative to SC/DE) or the comparison would be internally inconsistent about which income enters which state's taxable base.

**Independent Test**: Configure a household with both a Social Security benefit and ordinary income, run a projection against NC, and confirm only the ordinary income contributes to NC's taxable base.

**Acceptance Scenarios**:

1. **Given** a household with a $30,000 Social Security benefit and $50,000 of ordinary income, **When** NC state tax is computed for tax year 2026, **Then** the result is based on $50,000 only (`50,000 * 3.99%` = $1,995.00), not $80,000.

---

### User Story 3 - Multi-decade projections see NC's legislated rate step-down (Priority: P3)

A household running a realistic multi-decade retirement projection that spans both the 2025 and 2026+ tax years wants each year taxed at NC's actual rate for that year, not one rate frozen across the whole horizon.

**Why this priority**: A real, already-legislated mechanic (unlike SC's illustrative 2026→2027 step) that a long-horizon projection — this tool's actual use case — will cross in practice.

**Independent Test**: Run a projection whose horizon includes both tax year 2025 and tax year 2026, and confirm the computed NC tax reflects 4.25% in 2025 and 3.99% from 2026 onward for the same income.

**Acceptance Scenarios**:

1. **Given** a fixed $80,000 ordinary income held constant across tax years 2025 and 2026, **When** NC state tax is computed for each year, **Then** the 2025 result ($3,400.00) is higher than the 2026 result ($3,192.00), reflecting the legislated step-down.

---

### Edge Cases

- A household member's income is entirely Social Security (ordinary income of $0): NC tax is $0, same as User Story 1's zero-income floor.
- A retiree's income would qualify for NC's Bailey-settlement exclusion in real life (a pre-8/12/1989-vested state/local/federal government or military pension) — the module cannot detect this case (see Assumptions) and taxes that income the same as any other ordinary income. This is a documented, deliberate limitation, not a silent mismodeling.
- A tax year outside the module's documented schedule range is requested: `UnsupportedTaxYearError` is raised, matching every other state/federal module's existing behavior — no NC-specific exception path.
- Very high ordinary income: the flat rate applies uniformly with no additional top bracket or cap, unlike SC's/DE's graduated tables — confirm no cliff or bracket-boundary artifact appears at any income level.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `compute_state_tax()` MUST accept `"NC"` as a valid state code, dispatching (via `STATE_MODULES`) to a new `tax/state/nc.py` module — no branching added to `compute_state_tax()` itself.
- **FR-002**: NC's `compute_tax(income, filer_ages, filing_status, tax_year) -> StateTaxResult` MUST match the exact signature every other registered state module already implements, per `specs/002-tax-calculation-engine/contracts/tax-api.md`.
- **FR-003**: NC MUST tax only `IncomeComponents.ordinary_income`; `social_security_gross_benefit` MUST NOT enter NC's taxable base, matching North Carolina's actual full exemption of Social Security benefits from state income tax.
- **FR-004**: NC MUST apply a single statutory flat rate to 100% of taxable ordinary income, with no bracket thresholds: 4.25% for tax year 2025, and 3.99% for tax year 2026 and all later documented years (the last legislated figure held flat across the rest of the module's documented horizon, matching the project's existing per-module convention for years beyond the last legislated change).
- **FR-005**: The flat-rate figure MUST ship as a `SourcedFigure` citing N.C. Gen. Stat. §105-153.7 (as amended by S.L. 2023-134) — confirmed against NCDOR's official Tax Rate Schedules page during this feature's research — with `verified=True` and a `last_verified` date of the research date, since (unlike SC's/DE's inherited unverified placeholders) this figure is being confirmed against a primary/authoritative source as part of this feature, not carried over as placeholder debt.
- **FR-006**: NC MUST NOT apply an age-based retirement-income exclusion analogous to SC's age-65 or DE's age-60 exclusion. North Carolina has no general age-based exclusion; its only comparable mechanism (the Bailey settlement, N.C. Gen. Stat. §105-134.6 history) is scoped to a narrow subset of retirement income identified by source and pre-8/12/1989 vesting date — not representable in `IncomeComponents`' current shape (see Assumptions) — and MUST NOT be approximated by reusing SC's/DE's age-threshold shape.
- **FR-007**: NC's taxable income floor MUST be $0 (no negative tax), consistent with SC's/DE's/FL's existing floor behavior.
- **FR-008**: Registering NC MUST require no changes to `compute_state_tax()`'s own logic, `comparison/`, `simulation/`, the BFF, or the UI beyond confirming the existing `STATE_MODULES`-driven reference/dropdown plumbing (`services/bff/src/rp_bff/routes/reference.py`) surfaces `"NC"` automatically.
- **FR-009**: `docs/BRD.md` §2.3 (reference use case's candidate-state list) and §5.4 (state coverage table) MUST be updated to move North Carolina from the not-yet-implemented list into the implemented table, with its own structure/verification-status row.

### Key Entities *(include if feature involves data)*

- **NC flat-rate figure**: A `SourcedFigure` mapping tax year → single statutory rate (4.25% for 2025, 3.99% for 2026+), cited to N.C. Gen. Stat. §105-153.7. Structurally represented the same way SC's/DE's bracket tables are (a `BracketRow` sequence), but with exactly one row per year (`income_up_to=None`), since NC has no bracket thresholds at all — degenerately flat rather than approximately flat.
- **(No exclusion entity)**: Unlike SC's age-65 and DE's age-60 exclusion figures, NC's module introduces no analogous `SourcedFigure` — see FR-006 and Assumptions for why the real-world Bailey mechanism is out of scope rather than approximated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A household can select North Carolina as their state in an otherwise-unmodified projection and receive a tax result with no error, for any tax year already supported by the existing schedule horizon.
- **SC-002**: NC's computed tax for a documented tax year matches NCDOR's published flat rate for that year applied to ordinary income only, within floating-point rounding — verifiable against the worked examples in User Stories 1-3 above.
- **SC-003**: The full existing test suite (`pytest tests/`, `pytest services/bff/tests/`) continues to pass once NC is registered, with zero NC-specific special-casing added anywhere outside `tax/state/nc.py` and its one `STATE_MODULES` entry.
- **SC-004**: The BFF's existing reference/dropdown endpoint lists `"NC"` as soon as it is registered in `STATE_MODULES`, with no route code change required.

## Assumptions

- **Bailey settlement is out of scope for this pass.** NC's only mechanism comparable to SC's/DE's age-based exclusion — the Bailey settlement — exempts pre-8/12/1989-vested state/local/federal government and military pension income specifically, not income by age. `IncomeComponents` (the shared input every state module receives) carries a single blended `ordinary_income` figure with no income-source or pension-vesting-date breakdown, and today's Bailey-only reason for `IncomeComponents` field additions would exceed the bead's boundary (no changes to `comparison/`/`simulation/`, the packages that would need to supply that breakdown). NC's module therefore taxes 100% of `ordinary_income` at the flat rate and does not attempt to approximate Bailey with an age-based proxy — the bead's own acceptance criteria explicitly warns against assuming SC's/DE's age-65-exclusion shape applies here, and an age-based approximation would misrepresent NC law rather than honestly omit an unrepresentable case.
- **The historical $4,000/$8,000 non-Bailey retirement-benefit deduction** once codified at G.S. §105-134.6(b)(6) is treated as needing confirmation, not assumed present or absent — `plan.md`'s research phase will confirm its current status (whether it survived NC's 2014 flat-tax/standard-deduction simplification) before any figure referencing it is coded.
- **"Documented years" follows the existing per-module convention** (`tax/federal.py`, `sc.py`, `de.py`): the last legislated rate (3.99%, tax year 2026 onward) is held flat through the rest of the module's ~2020–2075 documented horizon. NCDOR notes that further revenue-trigger-conditioned cuts may apply starting tax year 2027, but those are not yet legislated, fixed figures, so they are not modeled or fabricated here — the same posture the project already takes toward any not-yet-triggered future change.
- **Tax years 2025 (4.25%) and 2026+ (3.99%) are treated as verified**, not inherited placeholder debt — both were checked against NCDOR's official Tax Rate Schedules page as part of this feature's own research, unlike SC's/DE's `verified=False` placeholders.
