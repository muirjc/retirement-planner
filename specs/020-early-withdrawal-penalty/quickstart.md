# Quickstart: Early-Withdrawal Penalty (Pre-59.5)

Validates the feature end-to-end: a voluntary Traditional withdrawal under 59.5 is penalized and
actually reduces balances (User Story 1), an unseasoned Roth conversion withdrawal contributes to
the same combined penalty (User Story 2), and a household unaffected by either condition sees no
change (SC-002) — per SC-001–SC-005.

## Prerequisites

- Python 3.11+, same environment as every prior engine feature.
- No config files, no network access — same offline posture as every prior engine feature.

## 1. A voluntary Traditional withdrawal under 59.5 is penalized and funded (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection, StrategyConfiguration

household = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
)
accounts = AccountBalances(traditional=200_000, roth=0, taxable=0)
strategy = StrategyConfiguration(
    label="early_withdrawal", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67},
)

result = run_plan_projection(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=20_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=65,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)

year_2026 = result.years[0]  # "you" is 55 -- under 59.5
traditional_draw = next(
    (item.amount for item in year_2026.mechanics.withdrawal_plan.sequence_withdrawals if item.account_type == "traditional"),
    0.0,
)
assert traditional_draw > 0.0
assert year_2026.early_withdrawal_penalty.penalty_owed == traditional_draw * 0.10

# Confirm the penalty actually reduced balances, not just reported: compare against a
# household with an identical draw but every member already 60+.
older_household = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=0)],
)
older_result = run_plan_projection(
    household=older_household, accounts=accounts,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=20_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=65,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)
assert older_result.years[0].early_withdrawal_penalty.penalty_owed == 0.0
assert result.years[0].ending_balances.traditional < older_result.years[0].ending_balances.traditional
```

**Expected outcome**: a household with a member under 59.5 taking a voluntary Traditional
withdrawal shows a nonzero penalty equal to 10% of that draw, and its projected balance is lower
than an otherwise-identical household whose only difference is having already cleared 59.5.

## 2. An unseasoned Roth conversion withdrawal contributes to the same combined penalty (User Story 2)

```python
strategy_with_ladder = StrategyConfiguration(
    label="ladder", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fixed_amount", conversion_bracket_ceiling_or_amount=90_000,
    conversion_window=(2026, 2026),
    claiming_ages={"you": 67},
)
household_ladder = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
)
result_ladder = run_plan_projection(
    household=household_ladder, accounts=AccountBalances(traditional=100_000, roth=0, taxable=0),
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=15_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=65,
    strategy=strategy_with_ladder, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)
flagged_year = next(y for y in result_ladder.years if y.unseasoned_roth_withdrawal > 0)
assert flagged_year.early_withdrawal_penalty.penalty_owed >= flagged_year.unseasoned_roth_withdrawal * 0.10
```

**Expected outcome**: a plan year 019 already flags for an unseasoned Roth withdrawal contributes
that same amount into this feature's own combined penalty base.

## 3. A household unaffected by either condition sees no change (SC-002)

```python
unaffected_household = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=65, ss_claim_age=67, ss_annual_benefit=0)],
)
unaffected_result = run_plan_projection(
    household=unaffected_household, accounts=AccountBalances(traditional=200_000, roth=0, taxable=0),
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=20_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=75,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)
assert all(y.early_withdrawal_penalty.penalty_owed == 0.0 for y in unaffected_result.years)
```

**Expected outcome**: identical to this feature not existing — a household whose every member is
always 60+ and never touches an unseasoned Roth conversion never sees a penalty.

## 4. Documentation check (User Story 3)

```bash
grep -A5 "72(t)(1)\|early-withdrawal penalty" docs/BRD.md
```

**Expected outcome**: `docs/BRD.md` describes the 10% early-withdrawal penalty (covering both
voluntary Traditional withdrawals and unseasoned Roth conversion principal) as modeled behavior,
and separately lists the disclosed remaining gaps (72(t)/SEPP, other statutory exceptions, the
separately-tracked IRMAA/NIIT funding gap).
