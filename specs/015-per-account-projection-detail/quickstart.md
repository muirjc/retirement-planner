# Quickstart: Per-Account Year-by-Year Projection Detail

Validates both user stories end-to-end: per-account balance/RMD/
withdrawal detail on a single result (US1, SC-001/SC-003/SC-004), and the
same detail independently viewable per candidate in a comparison (US2,
SC-005). Section 1-4 exercise the core library directly (no BFF/UI
needed); Section 5 is a manual walkthrough of the actual UI surfaces,
since rendering can't be captured in a runnable Python snippet.

## Prerequisites

- Python 3.11+, same environment as `001`–`014` (no new dependency).
- Scenario `b` (`config/scenarios/b.yaml`) — has two traditional accounts
  under different owners plus one inherited account, exercising every
  code path this feature touches.

## 1. Per-account figures sum back to the pooled totals they're derived from (SC-001)

```python
from retirement_planner.scenario import load_scenario  # or parse_scenario() directly on a YAML string
from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.reporting import compute_account_shares, attribute_plan_projection

scenario = load_scenario("b")  # or build a Scenario directly, matching config/scenarios/b.yaml's shape
strategy = StrategyConfiguration(
    label="base_case", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={m.person_name: m.ss_claim_age for m in scenario.household.members},
)

projection = run_plan_projection(
    household=scenario.household, accounts=..., traditional_ownership_shares=...,
    inherited_accounts=..., annual_spending_need=scenario.spending.annual_need_real,
    state=scenario.state, reference_tax_year=2026, start_plan_year=1, start_tax_year=2026,
    plan_to_age=90, strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
)  # (resolve accounts/traditional_ownership_shares/inherited_accounts the same way
   # services/bff/src/rp_bff/resolution.py's resolve_run_context() already does)

shares = compute_account_shares(scenario.accounts)
detail = attribute_plan_projection(projection, shares)

for year_detail, year in zip(detail, projection.years):
    for account_type in ("traditional", "roth", "taxable"):
        pooled = getattr(year.ending_balances, account_type)
        attributed_sum = sum(
            row.ending_balance for row in year_detail.accounts
            if row.account_type == account_type
        )
        assert attributed_sum == pooled  # exact -- see research.md §2
```

## 2. Retained figures are exact, not attributed, in the common case (SC-002, SC-003)

```python
# A member who owns exactly one traditional account: that account's own
# rmd_amount must equal the member's own already-computed exact RMD --
# not merely close to it.
single_account_members = {
    account.owner for account in scenario.accounts
    if account.account_type == "traditional" and account.inherited is None
    and sum(1 for a in scenario.accounts if a.owner == account.owner and a.account_type == "traditional") == 1
}
for year_detail, year in zip(detail, projection.years):
    for row in year_detail.accounts:
        if row.account_type == "traditional" and row.owner in single_account_members:
            assert row.rmd_amount == year.member_rmd_amounts.get(row.owner, 0.0)
            assert row.attribution == "independently_tracked"
        elif row.account_type in ("traditional", "roth", "taxable") and row.account_id in {
            a.account_id for a in scenario.accounts if a.inherited is None
        }:
            # balance/withdrawal figures on ordinary accounts are always
            # disclosed as an apportionment, never presented as observed
            assert row.attribution in ("independently_tracked", "fixed_share_of_pooled_total")
```

## 3. Inherited accounts are exact by construction, never touched by share math (Edge Cases)

```python
inherited_ids = {a.account_id for a in scenario.accounts if a.inherited is not None}
for year_detail, year in zip(detail, projection.years):
    for row in year_detail.accounts:
        if row.account_id in inherited_ids:
            assert row.attribution == "independently_tracked"
            assert row.ending_balance == year.inherited_account_balances.get(row.account_id, 0.0)
            assert row.withdrawal_amount == year.inherited_account_distributions.get(row.account_id, 0.0)
```

## 4. Social Security is shown per member, never only as a household total (SC-002)

```python
for year_detail, year in zip(detail, projection.years):
    assert year_detail.member_social_security_benefits == year.member_social_security_benefits
    # present even before claiming -- 0.0, never missing (Edge Cases)
    for member in scenario.household.members:
        assert member.person_name in year_detail.member_social_security_benefits
```

## 5. Manual UI walkthrough (US1, US2 — requires the running app)

Per `README.md`'s "Running the full stack (API + UI)" section:

1. Start the BFF and Streamlit UI, load scenario `b`.
2. **Run Simulation** page: run a Monte Carlo simulation. Confirm a new
   year-by-year account table appears below the existing verification
   indicator, showing scenario `b`'s traditional/Roth/taxable/inherited
   accounts each with their own balance, RMD, and withdrawal columns per
   year, and each claiming member's own Social Security amount. Confirm
   the inherited account's row is visibly marked differently
   (`independently_tracked`) from the ordinary accounts
   (`fixed_share_of_pooled_total`). Change the "Detail path index"
   override and re-run; confirm the table reflects a different path.
3. **Compare** page: run a state comparison with 2+ candidates. Confirm
   each candidate has its own expandable year-by-year account detail,
   and that expanding one candidate's detail never shows another
   candidate's figures.
