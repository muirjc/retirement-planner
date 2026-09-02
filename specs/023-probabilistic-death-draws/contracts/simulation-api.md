# Contract: `retirement_planner.simulation` public API (addendum to `005`)

Extends `specs/005-simulation-engine/contracts/simulation-api.md`. Every existing signature keeps
every existing parameter and its existing meaning unchanged; this addendum lists only what's new.

## New module: `simulation.mortality`

```python
def generate_death_age_draws(
    household: Household,
    survival_curves: dict[str, SurvivalCurve],
    path_count: int,
    seed: int,
) -> list[dict[str, int | None]]:
    """Generates path_count independent per-member death-age draws, one
    dict per path (index i pairs with return_paths[i], exactly like
    return_paths itself pairs across a comparison's candidates). A single
    random.Random(seed) instance is consumed in a fixed order -- path 0's
    members in household.members order, then path 1's, etc., one
    rng.random() call per member per path -- so the sequence is fully
    determined by seed alone. Each draw is conditioned on that member's
    own current_age (data-model.md § Derived): the drawn age is always
    >= current_age, or None if the draw places that member past the
    survival curve's own documented age range (treated identically to
    predicted_death_age being unset -- survives the full horizon).
    Raises ValueError if path_count <= 0. Raises KeyError if any
    household member's person_name is missing from survival_curves.
    """
```

Data types: no new dataclass. Return shape documented in [data-model.md](../data-model.md) § Per-Path
Death Draw.

## Modified: `monte_carlo.run_simulation()`

```python
def run_simulation(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_paths: list[ReturnPath],
    candidate_label: str,
    survival_curves: dict[str, SurvivalCurve] | None = None,
    death_year_draws: list[dict[str, int | None]] | None = None,   # NEW
    inherited_accounts: list[InheritedAccountBalance] = [],
) -> SimulationRun:
```

**New parameter**: `death_year_draws`. `None` (the default) reproduces every existing caller's exact
current behavior byte-for-byte (FR-007) -- no new validation runs, no path's `Household` is
overridden. When given:

- Raises `ValueError` if `survival_curves` is `None` (data-model.md § Modified: `run_simulation()`).
- Raises `ValueError` if `len(death_year_draws) != len(return_paths)`.
- Raises `KeyError` if any `household.members[*].person_name` is missing from any entry in
  `death_year_draws`.
- Every validation above runs eagerly, before any path is scored -- same discipline this function's
  docstring already documents for `traditional_ownership_shares`/`survival_curves`.
- Path `i`'s call to `comparison.run_plan_projection()` runs against a per-path `Household` (built by
  the new private `_household_for_path()` helper -- data-model.md) reflecting `death_year_draws[i]`
  instead of `household` directly; every other per-path step (return substitution, the existing fresh
  `inherited_accounts` copy) is unchanged.
- `survival_adjusted_success_rate` (unchanged formula) is computed exactly as it is today, whenever
  `survival_curves is not None` -- unconditional on whether `death_year_draws` was also given (it is
  simply evaluated over whatever `path_results` this call produced).

**Reproducibility**: identical `household`/`survival_curves`/`return_paths`/`death_year_draws`/every
other parameter always produces identical `SimulationRun` output, regardless of serial vs. parallel
dispatch (unchanged guarantee, now also covering the new parameter).

## Modified: `compare.compare_states()`, `compare.compare_roth_conversion_strategies()`, `compare.compare_withdrawal_sequencing_strategies()`, `compare.compare_claiming_age_grid()`

Each gains exactly one new parameter, in the same position as the existing `survival_curves`
parameter:

```python
death_year_draws: list[dict[str, int | None]] | None = None,   # NEW
```

Forwarded unchanged to every candidate's own `run_simulation()` call -- identical placement and
behavior to how `survival_curves` already reaches every candidate. No other change to any of these
four functions' signatures, validation, or behavior.

## Consumption expectations for downstream features

- A caller wanting this capability must generate `death_year_draws` itself via
  `generate_death_age_draws()` (exactly as it already generates `return_paths` via
  `generate_return_paths()`) and pass the identical resulting list into every `run_simulation()`/
  `compare_*()` call across one comparison -- the paired-draw pattern this function does not enforce
  on the caller's behalf (mirrors `return_paths`' own existing contract).
- `comparison.run_plan_projection()` (`018`) is **unchanged** -- this feature never modifies that
  module. A path's own survivor-scenario behavior (filing status, survivor Social Security, spending
  reduction) is entirely a consequence of the `Household` object `run_simulation()` now builds and
  passes in per path, not of any new logic inside the projection loop itself.
- `services/bff` and `apps/streamlit_ui` need no change -- this capability is not wired into either
  (spec.md scope decision); a caller reaching `run_simulation()`/`compare_*()` directly (as this
  project's own test suite and any future BFF wiring would) is the only way to use it for now.
