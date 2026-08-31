# Quickstart: Federal & State Tax Calculation Engine

Validates the feature end-to-end: compute federal tax with real Social Security taxability, compute state tax through independent pluggable modules, and inspect every figure's citation/verification status — all without any network access, per SC-001–SC-006.

> **All dollar figures and rates below are illustrative placeholders**, chosen to demonstrate the API shape and the provisional-income/bracket mechanics clearly — they are **not** asserted as accurate to any specific real tax year. Federal Social Security provisional-income thresholds ($32,000 / $44,000 for MFJ) are the actual, longstanding statutory values (26 U.S.C. §86) and are safe to treat as real; every bracket table and exclusion amount is a round placeholder pending the citation/verification work called out in plan.md's Development Workflow gate — every `SourcedFigure` shipped with this feature starts `verified=False` until a human confirms it, exactly as this quickstart demonstrates in step 3.

## Prerequisites

- Python 3.11+, same environment as `001-scenario-config-management` (no new dependencies — see research.md §1).
- No config files, no network access, no working-directory assumptions — this feature takes all its inputs as function arguments.

## 1. Compute federal tax with real Social Security taxability (User Story 1)

```python
from retirement_planner.tax import IncomeComponents, compute_federal_tax

# Below the first provisional-income threshold: none of Social Security is taxable.
low_income = IncomeComponents(ordinary_income=10_000, social_security_gross_benefit=20_000)
result = compute_federal_tax(low_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
assert result.taxable_social_security == 0

# Between the two thresholds: up to 50% of Social Security becomes taxable.
mid_income = IncomeComponents(ordinary_income=25_000, social_security_gross_benefit=20_000)
result = compute_federal_tax(mid_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
assert 0 < result.taxable_social_security <= 20_000 * 0.50

# Above the second threshold: up to 85% of Social Security becomes taxable — never more.
high_income = IncomeComponents(ordinary_income=150_000, social_security_gross_benefit=20_000)
result = compute_federal_tax(high_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
assert result.taxable_social_security <= 20_000 * 0.85
assert result.federal_tax_owed > 0
```

**Expected outcome**: `taxable_social_security` moves through the 0% / up-to-50% / up-to-85% tiers as provisional income crosses each threshold (Acceptance Scenarios 1.2–1.4), and `federal_tax_owed` reflects genuine bracket math, not a flat shortcut (Acceptance Scenario 1.1).

## 2. Compute state tax through independent, pluggable modules (User Story 2)

```python
from retirement_planner.tax import IncomeComponents, compute_state_tax

income = IncomeComponents(ordinary_income=60_000, social_security_gross_benefit=20_000)

sc_result = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
de_result = compute_state_tax("DE", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
fl_result = compute_state_tax("FL", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)

assert sc_result.state_tax_owed > 0     # graduated-bracket state (Acceptance Scenario 2.2)
assert de_result.state_tax_owed > 0     # graduated-bracket state
assert fl_result.state_tax_owed == 0    # zero-income-tax state (Acceptance Scenario 2.3)
assert fl_result.figures_used == []     # FL needs no figures to know the answer is zero (FR-007)

# Computing one state's tax never affects another's (Acceptance Scenario 2.4) —
# nothing here is mutated by the calls above; a repeat call is independent:
assert compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026) == sc_result
```

**Expected outcome**: SC and DE (graduated-bracket) each produce a non-zero result from genuine bracket math specific to that state (Acceptance Scenario 2.1–2.2); FL (zero-tax) always returns zero with no figures consulted (Acceptance Scenario 2.3); results are independent of each other (Acceptance Scenario 2.4).

## 3. Inspect figure provenance, and see a scheduled rate change take effect (User Story 3)

```python
for figure in sc_result.figures_used:
    print(figure.name, figure.citation, figure.last_verified, figure.verified)
# e.g. sc_bracket_table  "SC Code Ann. §12-6-510 (placeholder — pending verification)"  2026-08-27  False
```

**Expected outcome**: every figure behind the SC result is individually named, cited, dated, and marked `verified=False` by default (Acceptance Scenario 3.1–3.2) — nothing is silently treated as settled fact.

```python
# SC's own bracket-table figure documents more than one tax year (the same
# mechanic GA/NC/MS's real, currently-scheduled changes will use once those
# states' modules are added as follow-on work, FR-012) — requesting two
# different documented years produces two different, independently correct
# results:
result_2026 = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2026)
result_2027 = compute_state_tax("SC", income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2027)
assert result_2026.state_tax_owed != result_2027.state_tax_owed  # the scheduled rate changed
```

**Expected outcome** (Acceptance Scenario 3.3): each year's result reflects that year's scheduled rate — proven here using SC's own figures rather than a not-yet-built state, since SC/DE/FL are the only modules FR-017 requires this feature to ship.

```python
from retirement_planner.tax import UnsupportedTaxYearError

try:
    compute_federal_tax(low_income, filer_ages=[67, 65], filing_status="married_filing_jointly", tax_year=2075)
    assert False, "expected UnsupportedTaxYearError"
except UnsupportedTaxYearError as e:
    print(e.figure_name, e.requested_year, e.available_years)
    # a year far outside any documented schedule is refused, not extrapolated
```

**Expected outcome** (Acceptance Scenario 3.4, FR-016): a tax year outside a figure's documented schedule raises `UnsupportedTaxYearError` naming the figure and year — the engine never guesses.

## Running the automated version

Once implemented, the equivalent assertions above are `tests/integration/test_tax_lifecycle.py`:

```bash
pytest tests/integration/test_tax_lifecycle.py -v
```

All steps passing is the acceptance bar for this feature — see [contracts/tax-api.md](./contracts/tax-api.md) for the exact function signatures exercised above.
