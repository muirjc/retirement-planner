# Data Model: Monte Carlo Per-Path Probabilistic Death Draws

## New: Per-Path Death Draw (`simulation.mortality`)

Not a new dataclass — a plain `list[dict[str, int | None]]`, exactly one entry per Monte Carlo path,
in path order (index `i` corresponds to `return_paths[i]`, mirroring `return_paths`' own existing
"structural pairing" convention, `005` data-model.md § `return_paths`). Each path's own entry is a
dict keyed by every household member's `person_name` present in the `survival_curves` this draw was
generated from:

```python
death_year_draws: list[dict[str, int | None]]
# death_year_draws[i][person_name] -> that path's own drawn death age for that member,
#                                      or None (survives the full modeled horizon)
```

- **Value shape**: an `int` (a whole-number age, always `>= that member's current_age` — research.md
  §4) or `None` ("no death within the survival curve's documented range", i.e. this path treats that
  member exactly as if `predicted_death_age` were never configured).
- **Coverage**: every key in `survival_curves` used to generate the draws appears in every path's
  dict — never a partial per-path key set (`generate_death_age_draws()` always draws once per
  covered member per path; there is no "sometimes skip a member" case).
- **Generation**: produced once, for all paths, by `generate_death_age_draws()` (see below) — never
  regenerated per comparison candidate (spec.md FR-005, Constitution's paired-draw standard pattern).
- **Consumption**: read by `monte_carlo.py`'s new `_household_for_path()` helper, one path at a time,
  to build that path's own `Household` copy before its `run_plan_projection()` call. Never stored on
  `SimulationRun` (mirrors `return_paths` itself not being stored there either — the caller keeps its
  own copy and correlates by index).

## New function: `generate_death_age_draws()` (`simulation.mortality`, NEW module)

```python
def generate_death_age_draws(
    household: Household,
    survival_curves: dict[str, SurvivalCurve],
    path_count: int,
    seed: int,
) -> list[dict[str, int | None]]: ...
```

- Raises `ValueError` if `path_count <= 0` (mirrors `generate_return_paths()`'s own precondition).
- Raises `KeyError` if any `household.members[*].person_name` is missing from `survival_curves`
  (mirrors `run_simulation()`'s own existing eager-coverage check for the same parameter, applied
  here at generation time instead).
- Deterministic order: one `random.Random(seed)` instance, consumed path-major — path 0's draws in
  `household.members` order (one `member`, one `rng.random()` call each), then path 1's, etc.
  (research.md §5).
- Each individual draw: `_draw_death_age(curve, current_age, rng)` — see Derived, below.

## Derived (computed per member per path by `_draw_death_age()`, not stored on any dataclass)

- **Reference survival probability** — `S(current_age)`, the value a member's draw is conditioned
  against (research.md §4):
  - `current_age <= 50` (today's `SURVIVAL_TABLE`'s lowest documented age): `1.0`.
  - `current_age > 110` (today's highest documented age): `curve.probabilities_by_age[110]`.
  - Otherwise: `curve.probabilities_by_age[current_age]` (a direct lookup — every whole age 50-110 is
    documented, and `HouseholdMember.current_age` is always an `int`, so no interpolation is ever
    needed).
- **Drawn death age** — the smallest documented age `a >= current_age` with
  `curve.probabilities_by_age[a] <= reference_survival * V` (`V = rng.random()`, one call per member
  per path), or `None` if no such age exists (the draw places this member past the curve's own
  documented range — research.md §4's inverse-CDF derivation).

## Modified: `run_simulation()` (`simulation.monte_carlo`, `005`)

Gains one new parameter:

```python
def run_simulation(
    ...,                                                       # every existing parameter, unchanged
    survival_curves: dict[str, SurvivalCurve] | None = None,   # existing
    death_year_draws: list[dict[str, int | None]] | None = None,   # NEW
    inherited_accounts: list[InheritedAccountBalance] = [],
) -> SimulationRun: ...
```

- `None` (the default): identical behavior to today (FR-007).
- When given: validated eagerly, before any path is scored (mirrors this function's own existing
  eager-validation convention for `traditional_ownership_shares`/`survival_curves`):
  - `survival_curves is None` → `ValueError` (research.md §3 — required so the existing
    citation-attachment code path already covers this feature's own `FigureUsage`, FR-009).
  - `len(death_year_draws) != len(return_paths)` → `ValueError`.
  - Any `household.members[*].person_name` missing from any path's draw dict → `KeyError` (mirrors
    the existing `survival_curves` coverage check's own error type and eagerness).
- Each path `i`'s own call to `run_plan_projection()` now runs against
  `_household_for_path(household, death_year_draws[i] if death_year_draws is not None else None)`
  instead of `household` directly (see below) — every other existing per-path step (return
  substitution, fresh `inherited_accounts` copy) is unchanged.

## New: `_household_for_path()` (private helper, `simulation.monte_carlo`)

```python
def _household_for_path(
    household: Household, death_year_draw: dict[str, int | None] | None
) -> Household: ...
```

- `death_year_draw is None` → returns `household` unchanged (the same object — no copy, no-op).
- Otherwise → a new `Household` (`dataclasses.replace()`) whose `members` are each a
  `dataclasses.replace()` of the original member with `predicted_death_age=death_year_draw[member.person_name]`
  — this **replaces**, never merges with, the household's own statically-configured value for that
  path (spec.md FR-001). Every other field of `household` and of each member is unchanged.

## Modified: `compare_states()`, `compare_roth_conversion_strategies()`, `compare_withdrawal_sequencing_strategies()`, `compare_claiming_age_grid()` (`simulation.compare`, `005`)

Each gains one new, purely-passthrough parameter, `death_year_draws: list[dict[str, int | None]] |
None = None`, forwarded unchanged to every candidate's own `run_simulation()` call — identical
placement and behavior to how `survival_curves` already reaches every candidate today. No other
change to any of these four functions (research.md §2).

## Relationships

- `death_year_draws[i]` and `return_paths[i]` are independent, uncorrelated draws that happen to
  share the same path index `i` (spec.md Assumptions — no joint/correlated sampling); pairing them is
  purely positional bookkeeping so that path `i`'s market outcome and path `i`'s mortality outcome are
  both reused, together, across every comparison candidate.
- `survival_curves` now has two independent consumers within one `run_simulation()` call: the
  pre-existing post-hoc `survival_adjusted_success_rate` check (unconditional, evaluated once per
  path at that path's own shortfall year, if any) and, only when `death_year_draws` is also given,
  this feature's per-path `Household` override (already "baked into" `path_results` before either
  metric is computed) — the two are independent, coexist unreconciled, and are each individually
  gated exactly as documented above (research.md §3).
- A household with no member covered by `survival_curves` at all cannot use this feature at all
  (`death_year_draws` would itself be an empty-keyed, no-op draw set) — this feature only ever
  overrides a path's `predicted_death_age` for a member it actually drew a value for.
