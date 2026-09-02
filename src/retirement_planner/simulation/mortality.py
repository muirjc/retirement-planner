"""Per-path probabilistic death-age draws for Monte Carlo simulation
(023-probabilistic-death-draws, rp-vgv): seeded, deterministic generation
logic over simulation/survival_data.py's SurvivalCurve data, structurally
parallel to returns.py's generate_return_paths() -- generate once, reuse
path-for-path across every comparison candidate, exactly like return_paths
already is. See specs/023-probabilistic-death-draws/research.md and
contracts/simulation-api.md.

This module is a caller-invoked *generator* only -- it has no effect on
monte_carlo.run_simulation() by itself. A caller must pass this module's
output as run_simulation()'s own death_year_draws parameter to actually
apply it.
"""

from __future__ import annotations

import random

from retirement_planner.scenario import Household

from .models import SurvivalCurve


def _draw_death_age(curve: SurvivalCurve, current_age: int, rng: random.Random) -> int | None:
    """Draws one member's death age, conditioned on already being alive at
    current_age (research.md §4): standard inverse-transform sampling on
    the *conditional* survival function S(a)/S(current_age) for a >=
    current_age. Returns the smallest documented age >= current_age whose
    survival probability has dropped to or below a draw scaled by the
    reference survival probability at current_age, or None if no such age
    exists (the draw places this member past the curve's own documented
    range -- treated identically to predicted_death_age being unset,
    i.e. survives the full modeled horizon).

    reference_survival (S(current_age)) uses two documented boundary
    rules when current_age itself falls outside the curve's documented
    age range (data-model.md § Derived):
    - current_age <= the curve's lowest documented age (today, 50):
      1.0 -- "certain survival" to the table's own floor, deliberately
      reusing survival_data.py's own module-comment framing of age 50,
      even though its illustrative formula computes ~0.9948 there
      internally (research.md §4).
    - current_age > the curve's highest documented age (today, 110):
      the oldest documented probability -- since the subsequent search
      only considers documented ages >= current_age, and none exist
      above the table's own ceiling, this always resolves to None for
      such a member. A current_age already past the whole table's range
      is itself an implausible input this engine doesn't otherwise
      validate against -- a documented, known limitation, not silently
      miscomputed as a near-certain immediate death.
    - Otherwise: a direct lookup at current_age -- never interpolated.
      Every whole age in the documented range is itself documented (see
      survival_data.py's _build_illustrative_curve()), and
      HouseholdMember.current_age is always an int, so this direct
      lookup is exact, not an approximation.

    A structural (and intentional) consequence of this math: in the
    "otherwise" branch above, reference_survival equals S(current_age)
    exactly, and target_survival = reference_survival * draw is always
    strictly less than reference_survival (draw < 1.0, rng.random()'s own
    half-open range) -- so S(current_age) <= target_survival can never
    hold, meaning current_age itself is never returned as a drawn death
    age when it's a direct lookup. This is the correct reading of
    "conditioned on already alive at current_age", not an off-by-one bug:
    the member is alive *at* current_age by the conditioning itself, so
    the earliest possible new outcome is the next documented age onward.
    (The current_age <= lowest-documented-age branch has no such
    exclusion -- the lowest documented age itself remains reachable
    there, since reference_survival is 1.0, not that age's own S value.)
    """
    documented_ages = sorted(curve.probabilities_by_age)
    lowest_documented_age = documented_ages[0]
    highest_documented_age = documented_ages[-1]

    if current_age <= lowest_documented_age:
        reference_survival = 1.0
    elif current_age > highest_documented_age:
        reference_survival = curve.probabilities_by_age[highest_documented_age]
    else:
        reference_survival = curve.probabilities_by_age[current_age]

    draw = rng.random()  # V ~ Uniform[0, 1)
    target_survival = reference_survival * draw

    for age in documented_ages:
        if age < current_age:
            continue
        if curve.probabilities_by_age[age] <= target_survival:
            return age
    return None


def generate_death_age_draws(
    household: Household,
    survival_curves: dict[str, SurvivalCurve],
    path_count: int,
    seed: int,
) -> list[dict[str, int | None]]:
    """Generates path_count independent per-member death-age draws, one
    dict per path (index i pairs with the return_paths[i] a caller
    generated separately, via its own independent seed -- research.md
    §5's deliberate decoupling from the return-path RNG stream). A single
    random.Random(seed) instance is consumed in a fixed order -- path 0's
    members in household.members order, then path 1's, etc., one
    rng.random() call (inside _draw_death_age()) per member per path --
    so the sequence is fully determined by seed alone (FR-004).

    Each path's dict is keyed by every household member's person_name
    present in survival_curves; its value is that path's own drawn death
    age (int, always >= that member's current_age) or None ("survives the
    full modeled horizon" -- see _draw_death_age()).

    Raises ValueError if path_count <= 0 (mirrors generate_return_paths()'s
    own precondition). Raises KeyError if any household member's
    person_name is missing from survival_curves (mirrors
    run_simulation()'s own existing eager-coverage check for the same
    parameter, applied here at generation time instead) -- validated once,
    before any path is drawn.
    """
    if path_count <= 0:
        raise ValueError(f"path_count must be positive, got {path_count}")

    for member in household.members:
        if member.person_name not in survival_curves:
            raise KeyError(member.person_name)

    rng = random.Random(seed)
    draws: list[dict[str, int | None]] = []
    for _ in range(path_count):
        path_draw: dict[str, int | None] = {}
        for member in household.members:
            curve = survival_curves[member.person_name]
            path_draw[member.person_name] = _draw_death_age(curve, member.current_age, rng)
        draws.append(path_draw)
    return draws
