# Quickstart: Source-Attributed Retirement Income for State Exclusions (NC Bailey Settlement)

## Prerequisites

- Repo checked out on `027-nc-bailey-exclusion`, core deps installed.
- `pytest tests/` passing before starting (baseline for SC-004).

## 1. Compute NC tax directly with a Bailey exclusion (US1)

```python
from retirement_planner.tax.models import IncomeComponents
from retirement_planner.tax.state import compute_state_tax

# $40k Bailey-qualifying pension + $30k other ordinary income, tax year 2026 (3.99%)
income = IncomeComponents(
    ordinary_income=70_000.0,
    social_security_gross_benefit=0.0,
    government_pension_income=40_000.0,
)
result = compute_state_tax("NC", income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)
assert result.state_tax_owed == 30_000.0 * 0.0399  # $1,197.00 -- the $40k is excluded

# Entire ordinary income is Bailey-qualifying -> $0 NC tax
all_bailey = IncomeComponents(ordinary_income=50_000.0, social_security_gross_benefit=0.0, government_pension_income=50_000.0)
assert compute_state_tax("NC", all_bailey, filer_ages=[67], filing_status="single", tax_year=2026).state_tax_owed == 0.0

# No Bailey-qualifying income (field left at its 0.0 default) -> identical to 024-nc-state-tax's original behavior
unchanged = IncomeComponents(ordinary_income=80_000.0, social_security_gross_benefit=0.0)
assert compute_state_tax("NC", unchanged, filer_ages=[67], filing_status="single", tax_year=2026).state_tax_owed == 80_000.0 * 0.0399
```

## 2. Verify SC/DE/FL are unaffected by the new field (US3)

```python
# Same income, government_pension_income set -- SC/DE/FL never read it.
for state in ("SC", "DE", "FL"):
    with_flag = compute_state_tax(state, income, filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026)
    without_flag = compute_state_tax(
        state,
        IncomeComponents(ordinary_income=70_000.0, social_security_gross_benefit=0.0),
        filer_ages=[67], filing_status="married_filing_jointly", tax_year=2026,
    )
    assert with_flag.state_tax_owed == without_flag.state_tax_owed
```

## 3. Configure a Bailey-qualifying pension stream in a scenario (US1, US2)

```yaml
household:
  members:
    - person_name: "Alex"
      income_streams:
        - label: "State Teachers' Pension"
          stream_type: "pension"
          start_age: 65
          annual_amount: 40000
          inflation_adjustment: "cola_adjusted"
          bailey_qualifying: true   # NEW field -- pre-8/12/1989-vested government pension
state: "NC"
```

```python
from retirement_planner.scenario.loader import parse_scenario
scenario = parse_scenario(yaml_text, source="quickstart")
assert scenario.household.members[0].income_streams[0].bailey_qualifying is True
```

Run a projection for this household and confirm (US2): federal tax, FICA, IRMAA, and NIIT are
unchanged from an otherwise-identical household with no stream flagged `bailey_qualifying` (all
consume `ordinary_income`, which still includes the pension in full); only NC's own
`state_tax.state_tax_owed` is lower.

## 4. Run the test suites

```bash
pytest tests/                      # core: tax/state/test_nc.py, scenario round-trip, comparison-level test
pytest services/bff/tests/         # unaffected -- no BFF change in this feature
```

## Expected outcome

- A household with a stream marked `bailey_qualifying: true` and state `"NC"` pays NC tax on only
  the non-Bailey portion of their ordinary income.
- The same household's federal tax, FICA, IRMAA, and NIIT are unchanged — the Bailey exclusion is
  NC-state-only, never a federal or cross-cutting reduction (US2, FR-003).
- SC, DE, and FL compute identical results whether or not a stream is marked `bailey_qualifying`
  (US3, FR-006) — every existing SC/DE/FL test continues to pass unmodified.
- An existing scenario YAML with no `bailey_qualifying` field parses and projects identically to
  before this feature (FR-002).
- `docs/BRD.md` §5.4's NC row records Bailey-settlement support.
