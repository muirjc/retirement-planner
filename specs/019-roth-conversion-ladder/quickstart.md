# Quickstart: Roth Conversion Ladder (Five-Year Rule) Tracking

Validates the feature end-to-end: a withdrawal that reaches into an unseasoned conversion while a
household member is under 59.5 is flagged (User Story 1), multiple lots season and draw down
independently oldest-first (User Story 2), and a household with no Roth conversion is completely
unaffected (SC-004) — per SC-001–SC-006.

## Prerequisites

- Python 3.11+, same environment as every prior engine feature.
- No config files, no network access — same offline posture as every prior engine feature.

## 1. An unseasoned conversion withdrawal is flagged, then stops being flagged once seasoned (User Story 1, SC-001/SC-002)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection, StrategyConfiguration

household = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=55, ss_claim_age=67, ss_annual_benefit=0)],
)
accounts = AccountBalances(traditional=100_000, roth=0, taxable=0)
strategy = StrategyConfiguration(
    label="ladder", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy="fixed_amount", conversion_bracket_ceiling_or_amount=90_000,
    conversion_window=(2026, 2026),  # a single conversion in the first plan year
    claiming_ages={"you": 67},
)

result = run_plan_projection(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=15_000,  # exhausts Traditional in year 1, forcing a Roth draw every year after
    state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=65,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)

# 2026: the conversion executes; Traditional still covers spending -- no draw against
# the new lot yet (Edge Cases: a same-year conversion is never its own year's draw source).
year_2026 = next(y for y in result.years if y.tax_year == 2026)
assert year_2026.mechanics.conversion.amount_converted > 0
assert year_2026.unseasoned_roth_withdrawal == 0.0

# 2027-2030: Traditional is exhausted, so every year's spending need draws from Roth --
# "you" is 56-59 (under 59.5) and the conversion (2031 seasoning date) is still
# unseasoned, so every one of these draws is flagged in full.
for tax_year in (2027, 2028, 2029, 2030):
    year = next(y for y in result.years if y.tax_year == tax_year)
    roth_draw = next(
        (item.amount for item in year.mechanics.withdrawal_plan.sequence_withdrawals if item.account_type == "roth"),
        0.0,
    )
    assert roth_draw > 0.0
    assert year.unseasoned_roth_withdrawal == roth_draw  # the whole draw came from the unseasoned lot

# 2031: the conversion has now seasoned (5 full tax years since 2026) -- the year's own
# Roth draw is no longer flagged, even though "you" is still under 59.5.
year_2031 = next(y for y in result.years if y.tax_year == 2031)
assert year_2031.unseasoned_roth_withdrawal == 0.0
```

**Expected outcome**: the conversion year itself never flags anything; every year a draw reaches
into the still-unseasoned conversion while the household member is under 59.5 is flagged with the
full amount touched; the moment the conversion's own 5-year clock closes, the identical kind of
draw stops being flagged.

## 2. Once every member clears 59.5, no flag is raised even for an unseasoned lot (SC-002)

```python
# Same shape, but "you" starts at 59 instead of 55 -- by the time Traditional is
# exhausted and Roth draws begin (2027), "you" is already 60.
household_older = Household(
    filing_status="single",
    members=[HouseholdMember(person_name="you", current_age=59, ss_claim_age=67, ss_annual_benefit=0)],
)
result_older = run_plan_projection(
    household=household_older, accounts=accounts,
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=15_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=70,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)
year_2027_older = next(y for y in result_older.years if y.tax_year == 2027)  # "you" is 60 this year
roth_draw_2027_older = next(
    (item.amount for item in year_2027_older.mechanics.withdrawal_plan.sequence_withdrawals if item.account_type == "roth"),
    0.0,
)
assert roth_draw_2027_older > 0.0  # the draw still happens, and still touches the unseasoned lot...
assert year_2027_older.unseasoned_roth_withdrawal == 0.0  # ...but is never flagged, since "you" is already 60
```

**Expected outcome**: once every household member has reached 60, no flag occurs for that
household's draws, regardless of any lot's own seasoning status or the amount drawn.

## 3. A household with no Roth conversion is completely unaffected (SC-004)

```python
no_conversion_strategy = StrategyConfiguration(
    label="no_conversion", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67},
)
result_no_conversion = run_plan_projection(
    household=household, accounts=AccountBalances(traditional=100_000, roth=50_000, taxable=0),
    traditional_ownership_shares={"you": 1.0},
    annual_spending_need=15_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=65,
    strategy=no_conversion_strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.0),
)
assert all(y.unseasoned_roth_withdrawal == 0.0 for y in result_no_conversion.years)
```

**Expected outcome**: identical to this feature not existing — a pre-existing Roth balance drawn
down with no conversion ever executed never raises a flag, no matter the household member's age.

## 4. Documentation check (User Story 3)

```bash
grep -A5 "conversion-ladder\|408A(d)(3)(F)\|unseasoned" docs/BRD.md
```

**Expected outcome**: `docs/BRD.md`'s Roth conversion section describes conversion-lot seasoning
tracking and the unseasoned-withdrawal flag as modeled behavior, and separately lists the disclosed
remaining gaps (no penalty dollar amount, no per-member ownership, no earnings-qualified-distribution
rule).
