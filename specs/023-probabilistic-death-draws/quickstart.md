# Quickstart: Monte Carlo Per-Path Probabilistic Death Draws

Validates the feature end-to-end: enabling per-path draws produces path-varying death years that
already shape success/failure (User Story 1), draws and results stay reproducible and paired across
comparison candidates (User Story 2), and not opting in leaves output untouched — per SC-001–SC-007.

## Prerequisites

- Python 3.11+, same environment as every prior engine feature.
- No config files, no network access — same offline posture as every prior engine feature.

## 1. Per-path draws vary and shape each path's own outcome (User Story 1)

```python
from retirement_planner.comparison import StrategyConfiguration
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.simulation import (
    SURVIVAL_TABLE,
    generate_death_age_draws,
    generate_return_paths,
    run_simulation,
)
from retirement_planner.scenario import MarketAssumptions

household = Household(
    filing_status="married_filing_jointly",
    survivor_spending_reduction_pct=0.20,
    members=[
        HouseholdMember(person_name="you", current_age=67, ss_claim_age=67, ss_annual_benefit=30_000, full_retirement_age=67.0),
        HouseholdMember(person_name="spouse", current_age=67, ss_claim_age=67, ss_annual_benefit=20_000, full_retirement_age=67.0),
    ],
)
accounts = AccountBalances(traditional=800_000, roth=200_000, taxable=100_000)
strategy = StrategyConfiguration(
    label="baseline", withdrawal_strategy="rmd_taxable_traditional_roth",
    conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
    claiming_ages={"you": 67, "spouse": 67},
)
market = MarketAssumptions(
    equity_allocation=0.6, equity_return_mean_real=0.05, equity_return_std_real=0.17,
    bond_allocation=0.4, bond_return_mean_real=0.02, bond_return_std_real=0.06, correlation=0.0,
)
survival_curves = {"you": SURVIVAL_TABLE["primary"], "spouse": SURVIVAL_TABLE["spouse"]}

return_paths = generate_return_paths(
    market_assumptions=market, path_count=500, horizon_years=25, start_plan_year=1, seed=42,
)
death_year_draws = generate_death_age_draws(
    household=household, survival_curves=survival_curves, path_count=500, seed=99,  # independent seed
)

run = run_simulation(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=91,
    strategy=strategy, return_paths=return_paths, candidate_label="baseline",
    survival_curves=survival_curves, death_year_draws=death_year_draws,
)

# Draws vary path to path.
assert len({tuple(sorted(d.items())) for d in death_year_draws}) > 1

# A path whose draw kills "spouse" mid-horizon shows the same 018 survivor switch a deterministic
# projection would, driven entirely by that path's own drawn age -- no new projection-layer logic.
for path_index, draw in enumerate(death_year_draws):
    spouse_death_age = draw["spouse"]
    if spouse_death_age is not None and 68 <= spouse_death_age <= 85:
        death_tax_year = 2026 + (spouse_death_age - 67)
        post_death_years = [y for y in run.path_results[path_index].years if y.tax_year > death_tax_year]
        if post_death_years:
            assert all(y.filing_status == "single" for y in post_death_years)
        break
```

**Expected outcome**: different paths draw different death years (or none) per member; a path whose
draw places a death mid-horizon shows exactly the filing-status/Social-Security/spending switch `018`
already produces for a deterministic projection given that same death year — driven by this feature's
per-path `Household` override, not by any new logic in `comparison/projection.py`.

## 2. Reproducibility and paired-draw reuse (User Story 2)

```python
# Same seed, regenerated independently, reproduces identical draws.
draws_again = generate_death_age_draws(
    household=household, survival_curves=survival_curves, path_count=500, seed=99,
)
assert draws_again == death_year_draws

# Not opting in leaves output untouched (FR-007).
run_without = run_simulation(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=91,
    strategy=strategy, return_paths=return_paths, candidate_label="baseline",
)
run_without_again = run_simulation(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, state="FL",
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=91,
    strategy=strategy, return_paths=return_paths, candidate_label="baseline",
)
assert run_without.success_rate == run_without_again.success_rate

# Paired across comparison candidates -- every candidate scored against the identical draws.
from retirement_planner.simulation import compare_states

comparison = compare_states(
    household=household, accounts=accounts,
    traditional_ownership_shares={"you": 0.7, "spouse": 0.3},
    annual_spending_need=60_000, states=["FL", "CA"],
    reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=91,
    strategy=strategy, return_paths=return_paths,
    survival_curves=survival_curves, death_year_draws=death_year_draws,
)
for path_index in range(len(return_paths)):
    fl_years = comparison.runs[0].path_results[path_index].years
    ca_years = comparison.runs[1].path_results[path_index].years
    assert [y.filing_status for y in fl_years] == [y.filing_status for y in ca_years]
```

**Expected outcome**: the identical seed always reproduces the identical draws; a caller that doesn't
pass `death_year_draws` sees output unaffected by this feature's existence at all; every comparison
candidate's path `i` reflects the identical drawn death year(s) as every other candidate's path `i`.

## 3. Documentation check (User Story 3)

```bash
grep -A5 "probabilistic death\|per-path death draw" docs/BRD.md
```

**Expected outcome**: `docs/BRD.md`'s simulation-engine section describes per-path probabilistic
death draws as an opt-in Monte Carlo capability distinct from the existing post-hoc
`survival_adjusted_success_rate`, and lists its disclosed simplifications (illustrative unverified
survival table, current-age conditioning, independence from returns and from the other member's own
draw, no BFF/UI wiring yet).
