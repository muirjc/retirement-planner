# Quickstart: Survivor Scenario Projection Wiring

Validates the feature end-to-end: a configured death mid-horizon switches filing status, Social
Security income, and spending need for every plan year after it (User Story 1), the same switch
propagates into strategy comparisons with no extra wiring (User Story 2), and a household with no
configured death is completely unaffected (SC-002) — per SC-001–SC-006.

## Prerequisites

- Python 3.11+, same environment as every prior engine feature.
- No config files, no network access — same offline posture as every prior engine feature.

## 1. A configured death switches filing status, Social Security, and spending mid-horizon (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection, StrategyConfiguration

household = Household(
    filing_status="married_filing_jointly",
    survivor_spending_reduction_pct=0.20,  # 20% spending reduction after death
    members=[
        HouseholdMember(
            person_name="you", current_age=67, ss_claim_age=67,
            ss_annual_benefit=30_000, full_retirement_age=67.0,
        ),
        # This member is predicted to die at age 70 -- 3 years into the horizon.
        HouseholdMember(
            person_name="spouse", current_age=67, ss_claim_age=67,
            ss_annual_benefit=20_000, full_retirement_age=67.0, predicted_death_age=70,
        ),
    ],
)
accounts = AccountBalances(traditional=800_000, roth=200_000, taxable=100_000)
strategy = StrategyConfiguration(
    label="baseline", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67, "spouse": 67},
)

result = run_plan_projection(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=80,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)

# 2026: "spouse" is 67; dies at 70 in tax year 2029 -- that year is still MFJ.
death_year = next(y for y in result.years if y.tax_year == 2029)
assert death_year.filing_status == "married_filing_jointly"
assert death_year.member_social_security_benefits["spouse"] > 0  # still alive/claimed all of 2029

# 2030 onward: single, survivor benefit only, reduced spending.
first_post_death_year = next(y for y in result.years if y.tax_year == 2030)
assert first_post_death_year.filing_status == "single"
assert first_post_death_year.member_social_security_benefits["spouse"] == 0.0
assert first_post_death_year.member_social_security_benefits["you"] == 30_000.0  # higher of the two survives
assert first_post_death_year.effective_spending_need == 60_000 * 0.80  # 20% reduction applied
```

**Expected outcome**: every plan year through the configured death year is unaffected;
every plan year after switches to `single` filing, the survivor-benefit Social Security amount, and
reduced spending — demonstrating the "widow's tax penalty" the tool could not previously show.

## 2. A household with no configured death is completely unaffected (SC-002 regression guard)

```python
household_no_death = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=30_000, full_retirement_age=67.0),
        HouseholdMember(person_name="spouse", current_age=67, ss_claim_age=67, ss_annual_benefit=20_000, full_retirement_age=67.0),
    ],
)
result_no_death = run_plan_projection(
    household=household_no_death, accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=80,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)
assert all(y.filing_status == "married_filing_jointly" for y in result_no_death.years)
assert all(y.effective_spending_need == 60_000 for y in result_no_death.years)
```

**Expected outcome**: identical to this feature not existing — no year's filing status, Social
Security income, or spending need is altered when `predicted_death_age` is never configured.

## 3. The switch propagates into strategy comparisons with no extra wiring (User Story 2)

```python
from retirement_planner.comparison import compare_withdrawal_sequencing_strategies

comparison = compare_withdrawal_sequencing_strategies(
    household=household,  # the death-configured household from step 1
    accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=80,
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    candidates=[
        StrategyConfiguration(
            label="taxable_first", withdrawal_strategy="rmd_taxable_traditional_roth",
            conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
            claiming_ages={"ignored": 0},
        ),
        StrategyConfiguration(
            label="traditional_first", withdrawal_strategy="rmd_traditional_taxable_roth",
            conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
            claiming_ages={"ignored": 0},
        ),
    ],
    claiming_ages={"you": 67, "spouse": 67},
)
for projection in comparison.projections:
    post_death_years = [y for y in projection.years if y.tax_year >= 2030]
    assert all(y.filing_status == "single" for y in post_death_years)
```

**Expected outcome**: every candidate independently shows the same post-death switch — no
comparison-layer code needed to be touched for this to work (research.md Decision 6).

## 4. Documentation check (User Story 3)

```bash
grep -A5 "predicted_death_age\|survivor benefit" docs/BRD.md
```

**Expected outcome**: `docs/BRD.md`'s Social Security / projection-engine section describes the
mid-horizon filing-status switch, survivor Social Security income, and spending-reduction assumption
as modeled behavior, and separately lists the disclosed remaining gaps (Monte Carlo per-path wiring,
no Qualifying Surviving Spouse / MFJ-in-year-of-death status, no remarriage, no detailed budget
re-plan, no second-death handling).
