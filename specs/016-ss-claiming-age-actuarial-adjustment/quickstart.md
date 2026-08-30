# Quickstart: Social Security Claiming-Age Actuarial Adjustment

Validates the feature end-to-end: a household member's paid Social Security benefit actually
changes with claiming age (User Story 1), every projection path derives it the same way (User
Story 2), and the adjustment rate is a cited, auditable figure (User Story 3) — per SC-001–SC-005.

## Prerequisites

- Python 3.11+, same environment as every prior engine feature.
- No config files, no network access — same offline posture as every prior engine feature.

## 1. The claiming-age grid shows real trade-offs, not a flat "claim early" bias (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, compare_claiming_age_grid

household = Household(
    filing_status="single",
    members=[
        # ss_annual_benefit is now this member's PIA: $30,000 at FRA 67.
        HouseholdMember(
            person_name="alex", current_age=61, ss_claim_age=67,
            ss_annual_benefit=30_000, full_retirement_age=67.0,
        ),
    ],
)
accounts = AccountBalances(traditional=800_000, roth=200_000, taxable=100_000)

result = compare_claiming_age_grid(
    household=household, accounts=accounts,
    traditional_ownership_shares={"alex": 1.0},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=90,
    withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    claiming_age_grid=[{"alex": 62}, {"alex": 67}, {"alex": 70}],
)

for projection in result.projections:
    first_benefit_year = next(y for y in projection.years if y.member_social_security_benefits["alex"] > 0)
    print(projection.strategy.claiming_ages["alex"], first_benefit_year.member_social_security_benefits["alex"])
# Expect: 62 -> ~21,000 (≈70% of PIA)   67 -> 30,000 (exactly PIA)   70 -> ~37,200 (≈124% of PIA)
# Before this feature, every row printed 30,000 -- SC-001, SC-003.
```

## 2. A plain (non-grid) run uses the same adjusted amount (User Story 2)

```python
from retirement_planner.comparison import StrategyConfiguration, run_plan_projection

household.members[0].ss_claim_age = 64  # claiming 3 years before FRA 67
strategy = StrategyConfiguration(
    label="baseline", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"alex": 64},
)
projection = run_plan_projection(
    household=household, accounts=accounts, traditional_ownership_shares={"alex": 1.0},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=90,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)
first_benefit_year = next(y for y in projection.years if y.member_social_security_benefits["alex"] > 0)
print(first_benefit_year.member_social_security_benefits["alex"])
# Expect: a reduced amount (claiming 36 months early -> 20% reduction -> 24,000), not 30,000 -- SC-002.
```

## 3. The adjustment rate is a cited, auditable figure (User Story 3)

```python
year = first_benefit_year
ss_figures = [f for f in year.figures_used if f.name == "ss_claiming_age_adjustment_rates"]
print(ss_figures[0].citation, ss_figures[0].last_verified, ss_figures[0].verified)
# Expect: the 42 U.S.C. §402(q)/(w) citation, a last_verified date, and verified True once
# cross-checked at implementation time -- same FigureUsage shape as every other tax figure
# already surfaced this way (e.g. federal_brackets_mfj).
```

## 4. Omitting `full_retirement_age` reproduces prior behavior exactly (backward compatibility)

```python
member = HouseholdMember(person_name="jordan", current_age=63, ss_claim_age=64, ss_annual_benefit=28_000)
print(member.full_retirement_age)  # None until parse_scenario() resolves it
# After parse_scenario() resolution (or an equivalent direct default applied by the caller):
# full_retirement_age defaults to 64.0 (== ss_claim_age) -> zero adjustment -> paid benefit
# stays exactly 28,000, identical to this feature's absence. No existing scenario YAML file
# needs to change for this reason alone (research.md Decision 3).
```
