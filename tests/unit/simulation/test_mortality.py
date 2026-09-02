"""Unit tests for retirement_planner.simulation.mortality
(023-probabilistic-death-draws, rp-vgv): _draw_death_age()'s boundary
rules and inverse-CDF search, generate_death_age_draws()'s validation,
determinism, and distribution-level sanity (SC-002, SC-003 generation
half).
"""

from datetime import date

import pytest

from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.simulation.models import SurvivalCurve
from retirement_planner.simulation.mortality import _draw_death_age, generate_death_age_draws


class _FakeRng:
    """A stand-in for random.Random exposing only the one method
    _draw_death_age() calls, returning a fixed, caller-chosen value --
    lets each test pin the exact draw V without depending on a real
    seed's actual sequence."""

    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def _curve(probabilities_by_age: dict[int, float]) -> SurvivalCurve:
    return SurvivalCurve(
        person_name="you",
        probabilities_by_age=probabilities_by_age,
        citation="test fixture",
        last_verified=date(2026, 8, 28),
        verified=False,
    )


# A small, hand-picked curve -- documented ages 50/60/70/80/90, strictly
# decreasing probabilities -- chosen so each boundary case below can be
# worked out by hand rather than needing the real 61-entry SURVIVAL_TABLE.
_CURVE = _curve({50: 0.99, 60: 0.80, 70: 0.50, 80: 0.20, 90: 0.05})


def test_current_age_below_documented_range_uses_certain_survival_reference():
    # current_age=40 < lowest documented age 50 -> reference_survival=1.0,
    # target=1.0*0.5=0.5. Search ages>=40 (every documented age
    # qualifies): 50(0.99>0.5), 60(0.80>0.5), 70(0.50<=0.5) -> returns 70.
    assert _draw_death_age(_CURVE, current_age=40, rng=_FakeRng(0.5)) == 70


def test_current_age_below_documented_range_can_still_return_the_lowest_documented_age():
    # reference_survival=1.0 (not that age's own S value), so a draw close
    # to 1 can still land on the table's own lowest documented age.
    assert _draw_death_age(_CURVE, current_age=40, rng=_FakeRng(0.995)) == 50


def test_current_age_above_documented_range_always_returns_none():
    # current_age=95 > highest documented age 90 -> every documented age
    # is < current_age and therefore skipped, regardless of the draw.
    assert _draw_death_age(_CURVE, current_age=95, rng=_FakeRng(0.01)) is None
    assert _draw_death_age(_CURVE, current_age=95, rng=_FakeRng(0.99)) is None


def test_current_age_in_documented_range_uses_direct_lookup_not_interpolation():
    # current_age=70 is itself documented -> reference_survival=S(70)=0.50
    # directly, target=0.50*0.3=0.15. Search ages>=70: 70(0.50>0.15),
    # 80(0.20>0.15), 90(0.05<=0.15) -> returns 90.
    assert _draw_death_age(_CURVE, current_age=70, rng=_FakeRng(0.3)) == 90


def test_drawn_age_is_never_the_exact_current_age_itself_when_documented():
    # Structural property (mortality.py's own docstring): target is always
    # strictly less than reference_survival (draw < 1.0), so S(current_age)
    # <= target never holds for age == current_age in the direct-lookup
    # branch -- even a draw arbitrarily close to 1 returns the *next*
    # documented age, never current_age itself.
    assert _draw_death_age(_CURVE, current_age=70, rng=_FakeRng(0.999999)) == 80


def test_drawn_age_past_the_documented_range_returns_none():
    # current_age=90 (the highest documented age) with a very small draw:
    # target is tiny, no documented age's probability drops that low ->
    # this member "survives past the table" for this path.
    assert _draw_death_age(_CURVE, current_age=90, rng=_FakeRng(0.001)) is None


_HOUSEHOLD = Household(
    filing_status="married_filing_jointly",
    members=[
        # Ages chosen to match _CURVE's own documented ages exactly --
        # SurvivalCurve.survival_probability() (and this module's own
        # direct-lookup branch) never interpolates an undocumented age,
        # matching the real SURVIVAL_TABLE's "every whole age 50-110 is
        # documented" property this small test curve doesn't bother
        # replicating in full.
        HouseholdMember(person_name="you", current_age=70, ss_claim_age=67, ss_annual_benefit=30_000),
        HouseholdMember(person_name="spouse", current_age=60, ss_claim_age=67, ss_annual_benefit=20_000),
    ],
)
_SURVIVAL_CURVES = {"you": _CURVE, "spouse": _curve({50: 0.99, 60: 0.80, 70: 0.50, 80: 0.20, 90: 0.05})}


def test_generate_death_age_draws_rejects_non_positive_path_count():
    with pytest.raises(ValueError):
        generate_death_age_draws(
            household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=0, seed=1
        )


def test_generate_death_age_draws_raises_key_error_for_missing_member_curve():
    with pytest.raises(KeyError):
        generate_death_age_draws(
            household=_HOUSEHOLD, survival_curves={"you": _CURVE}, path_count=5, seed=1  # missing "spouse"
        )


def test_generate_death_age_draws_covers_every_member_every_path():
    draws = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=20, seed=1
    )
    assert len(draws) == 20
    assert all(set(draw) == {"you", "spouse"} for draw in draws)


def test_generate_death_age_draws_is_reproducible_for_the_same_seed():
    first = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=200, seed=42
    )
    second = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=200, seed=42
    )
    assert first == second


def test_generate_death_age_draws_differs_for_a_different_seed():
    first = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=200, seed=42
    )
    second = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=200, seed=43
    )
    assert first != second


def test_every_drawn_age_is_at_or_above_that_members_current_age():
    # SC-002: across a large sample, every non-None draw is plausible --
    # never a member "dying" before the age they already are.
    draws = generate_death_age_draws(
        household=_HOUSEHOLD, survival_curves=_SURVIVAL_CURVES, path_count=10_000, seed=7
    )
    for draw in draws:
        for member in _HOUSEHOLD.members:
            age = draw[member.person_name]
            if age is not None:
                assert age >= member.current_age
