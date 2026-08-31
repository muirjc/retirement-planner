# Quickstart: Social Security Spousal and Survivor Benefits

Validates the feature end-to-end: a lower-earning spouse's benefit is raised to the spousal floor in
every projection (User Story 1), the survivor-benefit calculation returns the correct higher-of-two
amount (User Story 2), and both rules are cited, auditable figures (User Story 3) — per SC-001–SC-005.

## Prerequisites

- Python 3.11+, same environment as every prior engine feature.
- No config files, no network access — same offline posture as every prior engine feature.

## 1. A lower-earning spouse's benefit is raised to the spousal floor (User Story 1)

```python
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.comparison import DeterministicReturnAssumption, run_plan_projection, StrategyConfiguration

household = Household(
    filing_status="married_filing_jointly",
    members=[
        # Higher earner: PIA $30,000 at FRA 67.
        HouseholdMember(
            person_name="you", current_age=67, ss_claim_age=67,
            ss_annual_benefit=30_000, full_retirement_age=67.0,
        ),
        # Lower earner: own PIA is only $6,000 -- well under 50% of the other's $30,000 ($15,000).
        HouseholdMember(
            person_name="spouse", current_age=67, ss_claim_age=67,
            ss_annual_benefit=6_000, full_retirement_age=67.0,
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
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=67,
    strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)

first_year = result.years[0]
assert first_year.member_social_security_benefits["spouse"] == 15_000.0  # 50% of $30,000, not the $6,000 PIA
assert first_year.member_social_security_benefits["you"] == 30_000.0     # unaffected -- already the higher earner
```

**Expected outcome**: the lower earner's Social Security income reflects the spousal-floor amount,
not their own smaller PIA-derived benefit — in an ordinary single projection, without needing the
claiming-age comparison grid at all (User Story 1's whole point: this needs no mortality/timeline
concept, only that both spouses are alive and MFJ).

## 2. The spousal floor never reduces a benefit that already meets it (SC-002 regression guard)

```python
household_no_floor_needed = Household(
    filing_status="married_filing_jointly",
    members=[
        HouseholdMember(person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=32_000, full_retirement_age=67.0),
        HouseholdMember(person_name="spouse", current_age=67, ss_claim_age=67, ss_annual_benefit=24_000, full_retirement_age=67.0),
    ],
)
# $24,000 already exceeds 50% of $32,000 ($16,000) -- the spousal floor must not apply here, and
# every existing test fixture in this repo uses a pair like this one (research.md Decision 5).
```

## 3. The survivor-benefit calculation returns the higher of two amounts (User Story 2)

```python
from retirement_planner.mechanics import compute_survivor_benefit

result = compute_survivor_benefit(member_a_benefit=30_000.0, member_b_benefit=12_000.0, tax_year=2026)
assert result.survivor_benefit == 30_000.0   # the higher amount continues, regardless of which member died
assert result.figures_used  # cites SS_SURVIVOR_BENEFIT_RULE

# Confirm this function has no caller yet inside the engine -- rp-g8y's job, not this feature's:
import inspect
from retirement_planner.comparison import projection as projection_module
source = inspect.getsource(projection_module)
assert "compute_survivor_benefit" not in source
```

**Expected outcome**: the calculation is correct and cited, but does not itself change any running
projection's output — confirmed here by checking `comparison/projection.py`'s own source has no call
to it (FR-007).

## 4. `HouseholdMember.predicted_death_age` is additive and opt-in (User Story 2)

```python
from retirement_planner.scenario import HouseholdMember

# Every existing scenario -- this constructor call included -- is unaffected: the field defaults
# to None and nothing in this feature (or any existing feature) consults it.
member = HouseholdMember(person_name="you", current_age=60, ss_claim_age=67, ss_annual_benefit=30_000)
assert member.predicted_death_age is None
```

## 5. Both rules are cited, dated, and auditable (User Story 3)

```python
from retirement_planner.mechanics.social_security_benefit import (
    SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT,
    SS_SURVIVOR_BENEFIT_RULE,
)

for figure in (SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT, SS_SURVIVOR_BENEFIT_RULE):
    print(figure.name, figure.citation, figure.last_verified, figure.verified)
```

**Expected outcome**: both figures print a specific statute/regulation citation and a last-verified
date, in the same structural pattern as `SS_CLAIMING_AGE_ADJUSTMENT` (016) and every other cited
figure in this codebase — nothing here is presented as settled without a traceable source
(constitution Principle III).

## 6. `docs/BRD.md` no longer implies spousal/survivor benefits are silently absent

Read `docs/BRD.md` §5.3 and §6.2a: the spousal floor and survivor-benefit calculation are described
as modeled behavior with their citations, and the remaining, genuinely unmodeled pieces (family
maximum benefit, deemed-filing mechanics, and — until `rp-g8y` ships — the mid-horizon projection
wiring itself) are named explicitly rather than left implicit (SC-005).

## Running the automated version

Once implemented, the equivalent assertions above live in
`tests/unit/mechanics/test_social_security_benefit.py` (spousal-floor and survivor-benefit formula
cases) and `tests/unit/comparison/test_projection.py` (the spousal floor applying inside a real
projection):

```bash
pytest tests/unit/mechanics/test_social_security_benefit.py tests/unit/comparison/test_projection.py -v
```

All steps passing is the acceptance bar for this feature — see
[contracts/mechanics-api.md](./contracts/mechanics-api.md) and
[contracts/scenario-api.md](./contracts/scenario-api.md) for the exact function/field signatures
exercised above.
