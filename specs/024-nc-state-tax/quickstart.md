# Quickstart: North Carolina State Income Tax Module

## Prerequisites

- Repo checked out on `024-nc-state-tax`, core deps installed.
- `pytest tests/` passing before starting (baseline for SC-003).

## 1. Compute NC tax directly

```python
from retirement_planner.tax.models import FilingStatus, IncomeComponents
from retirement_planner.tax.state import compute_state_tax

# US1.1: tax year 2026, flat 3.99%
income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
result = compute_state_tax("NC", income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)
assert result.state == "NC"
assert result.state_tax_owed == 80_000.0 * 0.0399  # $3,192.00

# US1.2: tax year 2025, flat 4.25% (one year ahead of the legislated step-down)
result_2025 = compute_state_tax("NC", income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2025)
assert result_2025.state_tax_owed == 80_000.0 * 0.0425  # $3,400.00

# US1.3: zero-income floor
zero_income = IncomeComponents(ordinary_income=0.0, social_security_gross_benefit=0.0)
result_zero = compute_state_tax("NC", zero_income, filer_ages=[67], filing_status="single", tax_year=2026)
assert result_zero.state_tax_owed == 0.0
```

## 2. Verify Social Security stays untaxed (US2)

```python
income = IncomeComponents(ordinary_income=50_000.0, social_security_gross_benefit=30_000.0)
result = compute_state_tax("NC", income, filer_ages=[67], filing_status="single", tax_year=2026)
assert result.state_tax_owed == 50_000.0 * 0.0399  # $30k SS never enters the base
```

## 3. Verify the legislated step-down across a multi-year horizon (US3)

```python
fixed_income = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
tax_2025 = compute_state_tax("NC", fixed_income, filer_ages=[67], filing_status="single", tax_year=2025)
tax_2026 = compute_state_tax("NC", fixed_income, filer_ages=[67], filing_status="single", tax_year=2026)
assert tax_2025.state_tax_owed > tax_2026.state_tax_owed  # 4.25% > 3.99%
```

## 4. Verify registration required no other code changes

```python
from retirement_planner.tax import STATE_MODULES
assert "NC" in STATE_MODULES
```

```bash
# BFF: confirms the reference route picks NC up with no route edit (data-model.md § Relationships)
pytest services/bff/tests/ -k reference
```

## 5. Run the test suites

```bash
pytest tests/                      # core: tax/state/test_nc.py + any STATE_MODULES-parametrized test
pytest services/bff/tests/         # reference/dropdown route
```

## Expected outcome

- Selecting `"NC"` as a household's state produces a real, cited tax result — no `KeyError`, no placeholder.
- NC's flat rate (4.25% in 2025, 3.99% from 2026 onward) applies to `ordinary_income` only; Social Security is never taxed.
- No age-based exclusion is applied — NC's module has none (research.md §3) — so a comparison against SC/DE will correctly show NC taxing 100% of ordinary income for every household, including one whose members are over 65/60.
- `pytest tests/` and `pytest services/bff/tests/` both pass with zero NC-specific special-casing outside `tax/state/nc.py` and its one `STATE_MODULES` entry.
- `docs/BRD.md` §2.3 and §5.4 reflect NC as implemented, with the same verification-status disclosure style SC/DE/FL already get — except NC's, honestly, says `verified=True` (research.md §2), not "unverified placeholder."
