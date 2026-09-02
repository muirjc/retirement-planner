# Research: FICA Payroll Tax on Earned-Income Streams

## 1. Module placement — `tax/`, not `mechanics/`

**Decision**: `tax/fica.py`, mirroring `tax/early_withdrawal_penalty.py`'s own reasoning verbatim: "a tax-liability concept ... not an account-mechanics concept."

**Rationale**: FICA is reported on payroll/Form 8959, not an account mechanic like a withdrawal or RMD. It takes a caller-computed base (each member's own `earned_income` stream total, already produced by `021`'s `compute_income_stream_amount()`) and applies statutory rates — exactly `compute_early_withdrawal_penalty()`'s own shape.

## 2. Where the "earned income only" base comes from

**Decision**: A new private helper in `comparison/projection.py`, `_member_earned_income_amounts()`, filters each member's `income_streams` to `stream_type == "earned_income"` and sums `compute_income_stream_amount()` results — independent of (and computed separately from) `021`'s existing `_member_income_stream_amounts()`, which pools every stream type together for the ordinary-income total.

**Rationale**: `_member_income_stream_amounts()` is already merged, shipped code with a documented shape (`021`'s own `contracts/comparison-api.md` addendum); changing its return shape to also split out earned-income-only amounts would touch an already-stable contract for a second feature's benefit. A second, independent helper keeps `021` and `022` decoupled — each stream's `compute_income_stream_amount()` is a cheap, pure, re-callable function (Constitution Principle VI: negligible cost), so recomputation is not a real performance concern.

**Alternatives considered**: *Extend `_member_income_stream_amounts()`'s return tuple.* Rejected for the coupling reason above — `022` should be a strictly additive consumer of `021`'s public surface (`IncomeStream.stream_type`, `compute_income_stream_amount()`), not a modifier of its already-shipped private plumbing.

## 3. Per-member OASDI/Medicare, household-level Additional Medicare Tax

**Decision**: `compute_fica_tax(member_earned_income: dict[str, float], filing_status: FilingStatus, tax_year: int) -> FicaTaxResult` computes OASDI and regular Medicare **per member** (each worker's own wage base cap applies to their own earnings only), but Additional Medicare Tax **once, at the household level**, against the *combined* earned income across every member.

**Rationale**: This matches real IRS mechanics exactly (not a simplification): the Social Security wage base is a per-worker annual limit (26 U.S.C. §3121); the Additional Medicare Tax threshold is filing-status-based and, for a married-filing-jointly household, applies to the couple's *combined* wages (reconciled on Form 8959) — a household where each spouse earns $150k (neither over the $200k single-equivalent per-employer withholding trigger) still owes Additional Medicare Tax on $50k of their combined $300k, because $300k exceeds the $250k MFJ threshold. Getting this right (rather than checking each member individually against a single-filer-shaped threshold) is exactly spec.md's Edge Case and User Story 3.

## 4. Wage base and thresholds — verified, cited figures

**Decision**:
- `OASDI_RATE` = 6.2%, `MEDICARE_RATE` = 1.45%, `ADDITIONAL_MEDICARE_TAX_RATE` = 0.9% — all fixed by statute.
- `OASDI_WAGE_BASE` = $184,500 — SSA's 2026 published taxable maximum. Pinned to this one value and held flat across every documented year, mirroring `tax/federal.py`'s own "real dollars, no further indexing engine" convention (the wage base is nominal-dollar and genuinely grows year to year in real life via national average wage indexing, not CPI — but this engine has no wage-growth projection any more than it has a CPI one outside `021`'s new `INFLATION_RATE`, so the same "pin one documented year, hold flat" treatment already applied to federal brackets/standard deduction/IRMAA tiers applies here too).
- `ADDITIONAL_MEDICARE_TAX_THRESHOLDS` = $200,000 (single) / $250,000 (MFJ) — genuinely fixed by IRC §3101(b)(2) since the tax took effect in 2013, not inflation-indexed. Holding these flat is not this engine's convention standing in for missing data — it is what the actual law does.

**Citations** (confirmed against primary/near-primary sources 2026-09-02, `verified=True`):
- OASDI rate, Medicare rate, wage base: SSA, "2026 Cost-of-Living Adjustment (COLA) Fact Sheet," https://www.ssa.gov/news/en/cola/factsheets/2026.html (states the $184,500 taxable maximum, the 6.2% OASDI rate, and the uncapped 1.45% HI rate directly); cross-referenced against SSA's own Contribution and Benefit Base page, https://www.ssa.gov/oact/cola/cbb.html.
- Additional Medicare Tax: 26 U.S.C. §3101(b)(2) (added by the Affordable Care Act, effective 2013); IRS, "Questions and Answers for the Additional Medicare Tax," https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax (confirms the $200,000/$250,000/$125,000 thresholds and that they are fixed, not inflation-indexed).

**Alternatives considered**: *Project the wage base forward using `021`'s new `INFLATION_RATE` (CPI-based).* Rejected — the wage base is indexed to the *national average wage index*, a different, faster-growing series than CPI; reusing the CPI figure for it would produce a wrong number dressed up as a citation, worse than the documented "pin one year, hold flat" simplification every other nominal-dollar figure in this engine already uses.

## 5. W-2 (employee-side) only, not SECA (self-employment)

**Decision**: Model only the 6.2%/1.45%/0.9% employee-side rates the originating issue names explicitly — not the 15.3% combined self-employment (SECA) rate a 1099/sole-proprietor household member would actually owe.

**Rationale**: The issue's own description gives the employee-side rates verbatim; `earned_income` (`021`) is a generic "wages during phased retirement" concept with no employment-type field to key a SECA-vs-W-2 branch off of. Modeling both would require a scope decision (a new `IncomeStream` field) `021` deliberately didn't make. Documented as an Assumption (spec.md) and in `docs/BRD.md`, not silently absorbed (Principle I) — a household whose phased-retirement earnings are genuinely self-employment income will see this feature understate their true payroll-tax cost.

## 6. No BFF or Streamlit-editing change needed

**Decision**: This feature adds no new scenario-configuration input (FICA is entirely *derived* from `021`'s already-configured `earned_income` streams) — so no BFF request-schema change, and no new Streamlit editing widget. The only UI change is a narration display addition (Streamlit reads the new `median_lifetime_fica_tax_paid` field off the summary response the BFF already serializes generically).

**Rationale**: Consistent with how `020-early-withdrawal-penalty` needed no new scenario input either (the early-withdrawal-penalty base is derived from already-configured ages and withdrawal amounts) — a "derived tax" feature, not a "new input" feature.
