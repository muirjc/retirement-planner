# Quickstart: Retirement Account Mechanics

Validates the feature end-to-end: compute an RMD via the correct table, draw down accounts in a swappable sequence, and execute a Roth conversion under a chosen strategy within a defined window — all without any network access, per SC-001–SC-006.

> **All dollar figures, ages, and divisors below are illustrative placeholders**, chosen to demonstrate the API shape and the RMD-table-selection/withdrawal/conversion mechanics clearly — they are **not** asserted as accurate to any specific real tax year, exactly as `002-tax-calculation-engine`'s quickstart notes for its own placeholder figures. Every `SourcedFigure` shipped with this feature (RMD-required starting age, Uniform Lifetime Table, Joint Life and Last Survivor Table) starts `verified=False` until a human confirms it against IRS Pub. 590-B, per plan.md's Development Workflow gate.

## Prerequisites

- Python 3.11+, same environment as `001` and `002` (no new dependencies — see research.md §1).
- No config files, no network access, no working-directory assumptions — this feature takes all its inputs as function arguments.

## 1. Compute an RMD with the correct table (User Story 1)

```python
from retirement_planner.mechanics import compute_rmd

# A single filer well past the RMD-required starting age: Uniform Lifetime Table.
result = compute_rmd(traditional_balance=1_000_000, member_age=75, tax_year=2026)
assert result.table_used == "uniform_lifetime"
assert result.required_amount > 0

# A married owner whose spouse is the sole beneficiary and >10 years younger:
# Joint Life and Last Survivor Table instead.
joint_result = compute_rmd(
    traditional_balance=1_000_000,
    member_age=75,
    tax_year=2026,
    spouse_age=60,
    spouse_is_sole_beneficiary=True,
)
assert joint_result.table_used == "joint_life"
# The Joint Life divisor is always larger (younger joint life expectancy),
# so the required amount is smaller for the same balance (Acceptance Scenario US1.2).
assert joint_result.required_amount < result.required_amount

# Below the RMD-required starting age: always $0, no table lookup needed.
too_young = compute_rmd(traditional_balance=1_000_000, member_age=60, tax_year=2026)
assert too_young.required_amount == 0
assert too_young.table_used is None
```

**Expected outcome**: the Uniform Lifetime Table is used by default (Acceptance Scenario US1.1), the Joint Life Table is used only for a sole-beneficiary spouse more than 10 years younger and produces a smaller required amount (Acceptance Scenario US1.2–1.3), and a member below the starting age always gets `$0` (Acceptance Scenario US1.4).

## 2. Draw funds in a defined, swappable sequence (User Story 2)

```python
from retirement_planner.mechanics import AccountBalances, compute_withdrawal_plan

balances = AccountBalances(traditional=500_000, roth=200_000, taxable=100_000)

# Default sequence: RMD, then taxable, then traditional, then Roth.
plan = compute_withdrawal_plan(spending_need=80_000, rmd_amount=40_000, starting_balances=balances)
assert plan.rmd_drawn == 40_000
assert plan.sequence_withdrawals[0].account_type == "taxable"
assert plan.shortfall == 0

# RMD alone can fully cover a smaller need — no further draws (Acceptance Scenario US2.2).
small_need_plan = compute_withdrawal_plan(spending_need=30_000, rmd_amount=40_000, starting_balances=balances)
assert small_need_plan.sequence_withdrawals == []

# Swapping the sequence changes draw order with zero code changes (Acceptance Scenario US2.5).
swapped_plan = compute_withdrawal_plan(
    spending_need=80_000, rmd_amount=40_000, starting_balances=balances,
    strategy="rmd_taxable_traditional_roth",  # the only strategy this feature ships (FR-005);
)                                              # a follow-on strategy would be selected the same way.

# An insufficient total balance reports a shortfall rather than a negative balance.
tiny_balances = AccountBalances(traditional=0, roth=0, taxable=1_000)
shortfall_plan = compute_withdrawal_plan(spending_need=50_000, rmd_amount=0, starting_balances=tiny_balances)
assert shortfall_plan.shortfall == 49_000
assert shortfall_plan.ending_balances.taxable == 0
```

**Expected outcome**: the default sequence draws RMD first, then taxable, then traditional, then Roth (Acceptance Scenario US2.1); a need already met by RMD triggers no further draws (US2.2); a shortfall is reported explicitly, never as a negative balance (US2.4).

## 3. Execute a Roth conversion within the configured window (User Story 3)

> `compute_roth_conversion()` takes an explicit `roth_balance` argument in addition to `traditional_balance` — added during implementation because `ConversionResult.ending_roth_balance` cannot be computed without it (see contracts/mechanics-api.md's implementation note). `tax_year` is held at 2026 below because `002`'s tax figures currently document only that year; `plan_year` (which controls window membership) is independent of `tax_year` and varies freely.

```python
from retirement_planner.mechanics import compute_roth_conversion

# Inside the window, filling to a bracket ceiling.
result = compute_roth_conversion(
    plan_year=2030,
    window=(2028, 2034),
    strategy="fill_to_bracket",
    bracket_ceiling_or_amount=206_000,     # illustrative MFJ 22%-bracket ceiling, matches 002's placeholder
    ordinary_income_established=120_000,   # this year's RMD + traditional withdrawals
    social_security_gross_benefit=0,       # simplified: no SS income yet this year
    filing_status="married_filing_jointly",
    tax_year=2026,
    traditional_balance=900_000,
    roth_balance=200_000,
)
assert result.amount_converted > 0
assert result.amount_converted == result.ordinary_income_added
assert result.ending_roth_balance == 200_000 + result.amount_converted

# Outside the window: no conversion occurs at all (Acceptance Scenario US3.2).
outside_window = compute_roth_conversion(
    plan_year=2035, window=(2028, 2034), strategy="fill_to_bracket",
    bracket_ceiling_or_amount=206_000, ordinary_income_established=120_000,
    social_security_gross_benefit=0, filing_status="married_filing_jointly",
    tax_year=2026, traditional_balance=900_000, roth_balance=200_000,
)
assert outside_window.amount_converted == 0

# A fixed-dollar-amount strategy converts exactly the configured amount (US3.3),
# capped at the available traditional balance if smaller.
fixed = compute_roth_conversion(
    plan_year=2030, window=(2028, 2034), strategy="fixed_amount",
    bracket_ceiling_or_amount=50_000, ordinary_income_established=120_000,
    social_security_gross_benefit=0, filing_status="married_filing_jointly",
    tax_year=2026, traditional_balance=900_000, roth_balance=200_000,
)
assert fixed.amount_converted == 50_000

# The two strategies produce different, independently correct results
# from the same inputs (Acceptance Scenario US3.6).
assert result.amount_converted != fixed.amount_converted
```

**Expected outcome**: a conversion inside the window under `fill_to_bracket` fills up to the configured ceiling (US3.1), no conversion happens outside the window (US3.2), `fixed_amount` converts exactly its configured amount or less if the balance is smaller (US3.3), and the two strategies never produce the same result from the same inputs by coincidence of shared logic (US3.6).

## 4. RMD dollars are never also converted (Edge Cases)

```python
from retirement_planner.mechanics import AccountBalances, compute_plan_year_mechanics

result = compute_plan_year_mechanics(
    plan_year=2030,
    tax_year=2026,  # held at 2026 — see the note in step 3 above
    spending_need=60_000,
    starting_balances=AccountBalances(traditional=900_000, roth=200_000, taxable=50_000),
    rmd_amount=40_000,
    social_security_gross_benefit=0,
    filing_status="married_filing_jointly",
    conversion_window=(2028, 2034),
    conversion_strategy="fill_to_bracket",
    conversion_bracket_ceiling_or_amount=206_000,
)
# The traditional balance the conversion drew against already excludes the RMD —
# conversion math started from (900_000 - 40_000), never from the pre-RMD 900_000.
assert result.withdrawal_plan.rmd_drawn == 40_000
assert result.conversion.ending_traditional_balance == 900_000 - 40_000 - result.conversion.amount_converted
```

**Expected outcome**: `compute_plan_year_mechanics()` computes the withdrawal plan (establishing `rmd_drawn` and the post-RMD traditional balance) before computing the conversion, so RMD dollars are structurally excluded from what's available to convert — consistent with the federal rule this feature encodes (FR-013).

## Running the automated version

Once implemented, the equivalent assertions above are `tests/integration/test_mechanics_lifecycle.py`:

```bash
pytest tests/integration/test_mechanics_lifecycle.py -v
```

All steps passing is the acceptance bar for this feature — see [contracts/mechanics-api.md](./contracts/mechanics-api.md) for the exact function signatures exercised above.
