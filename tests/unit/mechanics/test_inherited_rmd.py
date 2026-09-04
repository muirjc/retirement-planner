"""Unit tests for compute_inherited_rmd() (012-inherited-ira-rmd, US1;
divisor comparison for the non-EDB post-RBD case extended by rp-kn5).

Expected divisors/amounts are hand-calculated against
inherited_rmd.py's SINGLE_LIFE_EXPECTANCY_TABLE, verified against IRS Pub.
590-B (2025), Appendix B, Table I (rp-6c5) -- age 80's divisor (11.2) is
this table's real, IRS-published value. What's under test here is the
"look up once at death_year + 1, then subtract 1.0 per subsequent year"
divisor logic (research.md §7).

_COMMON_KWARGS's beneficiary_current_age is set to the *decedent's own*
translated age each year (80 in 2024, 81 in 2025, ...) -- not because
that's realistic, but because it makes the beneficiary's own divisor
identical to the decedent's own divisor every year, so these tests keep
exercising exactly the "look up once, decrement" mechanic the module
docstring above describes without also entangling the separate "longer
of" comparison rp-kn5 added (covered by its own dedicated tests below).
"""

import pytest

from retirement_planner.mechanics.inherited_rmd import (
    SINGLE_LIFE_EXPECTANCY_TABLE,
    compute_inherited_rmd,
)
from retirement_planner.tax import UnsupportedTaxYearError

_COMMON_KWARGS = dict(
    death_year=2023,
    decedent_age_at_death=80,
    decedent_was_taking_rmds=True,
    beneficiary_classification="non_eligible_designated_beneficiary",
)


def _same_age_as_decedent(tax_year: int) -> int:
    """This beneficiary's translated age, chosen so their own divisor
    equals the decedent's -- see module docstring above."""
    return 80 + (tax_year - 2024)


def test_initial_divisor_looked_up_at_decedent_age_for_the_year_after_death():
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, beneficiary_current_age=_same_age_as_decedent(2024),
        **_COMMON_KWARGS,
    )
    assert result.table_used == "single_life_expectancy"
    assert result.divisor == 11.2
    assert result.required_amount == pytest.approx(1_000_000 / 11.2)


def test_divisor_reduces_by_exactly_one_per_subsequent_year_not_a_fresh_lookup():
    year_1 = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, beneficiary_current_age=_same_age_as_decedent(2024),
        **_COMMON_KWARGS,
    )
    year_2 = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2025, beneficiary_current_age=_same_age_as_decedent(2025),
        **_COMMON_KWARGS,
    )
    year_3 = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2026, beneficiary_current_age=_same_age_as_decedent(2026),
        **_COMMON_KWARGS,
    )
    assert year_1.divisor == 11.2
    assert year_2.divisor == 10.2
    assert year_3.divisor == 9.2


def test_zero_or_negative_balance_is_always_zero_with_no_table_lookup():
    """No beneficiary_current_age needed here -- the balance<=0 shortcut
    returns before any divisor (beneficiary's or the decedent's) is ever
    consulted."""
    result = compute_inherited_rmd(inherited_balance=0, tax_year=2024, **_COMMON_KWARGS)
    assert result.required_amount == 0.0
    assert result.table_used is None
    assert result.divisor is None
    assert result.figures_used == []


def test_depletion_deadline_is_death_year_plus_ten():
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, beneficiary_current_age=_same_age_as_decedent(2024),
        **_COMMON_KWARGS,
    )
    assert result.depletion_deadline_year == 2033


def test_is_within_ten_year_window_true_through_deadline_year_false_after():
    within = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2033, beneficiary_current_age=_same_age_as_decedent(2033),
        **_COMMON_KWARGS,
    )
    after = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2034, beneficiary_current_age=_same_age_as_decedent(2034),
        **_COMMON_KWARGS,
    )
    assert within.is_within_ten_year_window is True
    assert after.is_within_ten_year_window is False


def test_figures_used_includes_the_single_life_expectancy_table():
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, beneficiary_current_age=_same_age_as_decedent(2024),
        **_COMMON_KWARGS,
    )
    figure_names = {f.name for f in result.figures_used}
    assert figure_names == {"single_life_expectancy_table"}


def test_single_life_expectancy_table_is_verified_and_covers_every_published_age():
    """Regression for rp-6c5: the table previously covered only ages
    50-95 (a subset) and shipped verified=False; it now covers every age
    IRS Pub. 590-B (2025), Appendix B, Table I publishes (0-120+) and has
    been cross-checked against that primary source."""
    assert SINGLE_LIFE_EXPECTANCY_TABLE.verified is True
    divisors = SINGLE_LIFE_EXPECTANCY_TABLE.value_for_year(2024)
    assert set(divisors) == set(range(0, 121))
    # Spot-checked against IRS Pub. 590-B (2025) pp. 50-51.
    assert divisors[0] == 84.6
    assert divisors[50] == 36.2
    assert divisors[72] == 17.2
    assert divisors[80] == 11.2
    assert divisors[120] == 1.0


def test_unsupported_divisor_year_raises():
    with pytest.raises(UnsupportedTaxYearError):
        compute_inherited_rmd(
            inherited_balance=1_000_000,
            tax_year=1999,
            death_year=1998,
            decedent_age_at_death=80,
            decedent_was_taking_rmds=True,
            beneficiary_classification="non_eligible_designated_beneficiary",
            beneficiary_current_age=80,
        )


# --- 013-inherited-ira-edge-cases: pre-RBD / Roth non-EDB (rp-l4d, rp-c8b) ---


def test_pre_rbd_non_edb_requires_no_annual_distribution():
    """research.md §1: Pub. 590-B p.10 -- "no distribution is required
    for any year before the 10th year" when the owner died before RBD."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000,
        tax_year=2024,
        death_year=2023,
        decedent_age_at_death=68,
        decedent_was_taking_rmds=False,
        beneficiary_classification="non_eligible_designated_beneficiary",
    )
    assert result.required_amount == 0.0
    assert result.table_used is None
    assert result.divisor is None
    assert result.figures_used == []
    assert result.depletion_deadline_year == 2033  # unchanged: death_year + 10


def test_roth_non_edb_requires_no_annual_distribution_even_if_decedent_was_taking_rmds():
    """research.md §2: a Roth account is always deemed pre-RBD --
    decedent_was_taking_rmds=True is ignored for account_type="roth"."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000,
        tax_year=2024,
        death_year=2023,
        decedent_age_at_death=80,
        decedent_was_taking_rmds=True,
        beneficiary_classification="non_eligible_designated_beneficiary",
        account_type="roth",
    )
    assert result.required_amount == 0.0
    assert result.table_used is None


def test_traditional_post_rbd_non_edb_is_unchanged_by_the_new_account_type_parameter():
    """Regression: account_type defaults to "traditional", reproducing
    012's own existing behavior exactly for every caller that doesn't
    pass it (same-age beneficiary per this module's docstring, so rp-kn5's
    "longer of" comparison doesn't itself change the number here)."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
        beneficiary_current_age=80,
    )
    assert result.divisor == 11.2


# --- rp-kn5: non-EDB post-RBD "longer of" comparison (previously missing --
# the decedent's divisor was used unconditionally, overstating the required
# distribution whenever the beneficiary is younger than the decedent) ---


def test_post_rbd_non_edb_uses_the_longer_of_beneficiary_or_owner_divisor():
    """Mirrors test_post_rbd_non_spouse_edb_uses_the_longer_of_..._divisor
    below -- same "longer of" rule, now also applied to a non-EDB
    beneficiary (rp-kn5): beneficiary (50) is much younger than the
    already-RMD-taking decedent (80) -- the beneficiary's own, longer
    life expectancy wins, not the decedent's shorter one."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
        beneficiary_current_age=50,
    )
    assert result.divisor == 36.2  # Table I, age 50 -- not the decedent's 11.2
    assert result.required_amount == pytest.approx(1_000_000 / 36.2)


def test_post_rbd_non_edb_falls_back_to_owner_divisor_when_beneficiary_is_older():
    """A beneficiary (90) older than the decedent (70) has a *shorter*
    own life expectancy -- the owner's side wins instead, reproducing
    012's original decedent-only result for this (uncommon) case."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=70,
        decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
        beneficiary_current_age=90,
    )
    assert result.divisor == 18.8  # Table I, age 70 (the decedent's) -- not the beneficiary's shorter one


def test_post_rbd_non_edb_divisor_decrements_by_one_each_subsequent_year():
    """The beneficiary side of the "longer of" comparison uses the same
    "look up once, decrement" method as every other divisor here -- never
    a fresh lookup at the beneficiary's later age."""
    kwargs = dict(
        inherited_balance=1_000_000, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
    )
    year_1 = compute_inherited_rmd(tax_year=2024, beneficiary_current_age=50, **kwargs)
    year_2 = compute_inherited_rmd(tax_year=2025, beneficiary_current_age=51, **kwargs)
    assert year_1.divisor == 36.2
    assert year_2.divisor == 35.2  # 36.2 - 1.0, not a fresh age-51 lookup (35.3)


def test_post_rbd_non_edb_requires_beneficiary_current_age():
    """A caller that omits beneficiary_current_age for a post-RBD non-EDB
    account now gets a loud failure, not a silently-wrong decedent-only
    result -- matching the EDB branches' existing discipline."""
    with pytest.raises(AssertionError):
        compute_inherited_rmd(
            inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=80,
            decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
        )


# --- 013-inherited-ira-edge-cases: EDB "stretch" (rp-iju) ---


def test_post_rbd_non_spouse_edb_uses_the_longer_of_beneficiary_or_owner_divisor():
    """research.md §3: beneficiary (50) is much younger than the
    already-RMD-taking decedent (80) -- the beneficiary's own, longer
    life expectancy wins ("longer of")."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="eligible_designated_beneficiary_other",
        beneficiary_current_age=50,
    )
    assert result.divisor == 36.2  # Table I, age 50 -- not the decedent's 11.2


def test_post_rbd_non_spouse_edb_falls_back_to_owner_divisor_when_beneficiary_is_older():
    """research.md §3: a beneficiary (90) older than the decedent (70)
    has a *shorter* own life expectancy -- the owner's side wins instead."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=70,
        decedent_was_taking_rmds=True, beneficiary_classification="eligible_designated_beneficiary_other",
        beneficiary_current_age=90,
    )
    assert result.divisor == 18.8  # Table I, age 70 (the decedent's) -- not the beneficiary's shorter one


def test_pre_rbd_non_spouse_edb_uses_only_the_beneficiary_s_own_divisor():
    """research.md §3: no "longer of" comparison pre-RBD -- there is no
    owner-RMD baseline to compare against."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=68,
        decedent_was_taking_rmds=False, beneficiary_classification="eligible_designated_beneficiary_other",
        beneficiary_current_age=50,
    )
    assert result.divisor == 36.2


def test_non_spouse_edb_divisor_decrements_by_one_each_subsequent_year():
    """research.md §3, §5: non-spouse EDB divisor is looked up once, then
    reduced by 1.0/year -- never a fresh lookup (unlike a spouse)."""
    kwargs = dict(
        inherited_balance=1_000_000, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="eligible_designated_beneficiary_other",
    )
    year_1 = compute_inherited_rmd(tax_year=2024, beneficiary_current_age=50, **kwargs)
    year_2 = compute_inherited_rmd(tax_year=2025, beneficiary_current_age=51, **kwargs)
    assert year_1.divisor == 36.2
    assert year_2.divisor == 35.2  # 36.2 - 1.0, not a fresh age-51 lookup (35.3)


def test_spouse_edb_divisor_is_recalculated_fresh_each_year_not_decremented():
    """research.md §4: Pub. 590-B p.9 -- "the applicable denominator
    continues to be determined each subsequent year using Table I" for a
    surviving spouse, contrasted against the non-spouse decrement rule."""
    kwargs = dict(
        inherited_balance=1_000_000, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="eligible_designated_beneficiary_spouse",
    )
    year_1 = compute_inherited_rmd(tax_year=2024, beneficiary_current_age=75, **kwargs)
    year_2 = compute_inherited_rmd(tax_year=2025, beneficiary_current_age=76, **kwargs)
    assert year_1.divisor == 14.8  # Table I, age 75
    assert year_2.divisor == 14.1  # Table I, age 76 (fresh) -- not 14.8 - 1.0 = 13.8


def test_spouse_edb_pre_rbd_delays_until_decedent_would_have_reached_rbd_age():
    """research.md §4: Pub. 590-B p.10 -- a spouse "isn't required to
    begin receiving minimum distributions until the end of the year in
    which the IRA owner would have reached their required beginning
    date." Decedent died at 60 in 2023 (born ~1963); RMD_START_AGE is 73
    -- would have reached RBD in 2036."""
    before = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2035, death_year=2023, decedent_age_at_death=60,
        decedent_was_taking_rmds=False, beneficiary_classification="eligible_designated_beneficiary_spouse",
        beneficiary_current_age=58,
    )
    at_rbd_year = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2036, death_year=2023, decedent_age_at_death=60,
        decedent_was_taking_rmds=False, beneficiary_classification="eligible_designated_beneficiary_spouse",
        beneficiary_current_age=59,
    )
    assert before.required_amount == 0.0
    assert before.table_used is None
    assert at_rbd_year.required_amount > 0.0
    assert at_rbd_year.divisor == 28.0  # Table I, spouse's own age 59


def test_edb_figures_used_always_names_the_single_life_expectancy_table():
    for classification in ("eligible_designated_beneficiary_spouse", "eligible_designated_beneficiary_other"):
        result = compute_inherited_rmd(
            inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=80,
            decedent_was_taking_rmds=True, beneficiary_classification=classification, beneficiary_current_age=50,
        )
        assert {f.name for f in result.figures_used} == {"single_life_expectancy_table"}


def test_custom_depletion_deadline_year_overrides_the_death_year_plus_ten_default():
    """research.md §5, §6: the caller's own already-computed authoritative
    deadline (e.g. a minor child's majority_year + 10, or a true EDB's
    far-future sentinel) is used as-is when given."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2023, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="eligible_designated_beneficiary_other",
        beneficiary_current_age=8, depletion_deadline_year=2223,
    )
    assert result.depletion_deadline_year == 2223
    assert result.is_within_ten_year_window is True


# --- rp-bdb: pre-SECURE-Act (pre-2020) death grandfathered under the
# pre-Act rules, regardless of beneficiary_classification. death_year=2018
# with tax_year=2019 (the year immediately after death, so
# initial_divisor_year == tax_year and beneficiary_current_age maps
# directly onto it) keeps these tests exercising the same clean divisor
# arithmetic as the rest of this file. ---


def test_pre_secure_act_death_default_deadline_has_no_forced_depletion():
    """A caller that omits depletion_deadline_year for a pre-2020 death
    gets the same far-future sentinel a true EDB gets post-Act -- not
    death_year + 10 -- since the 10-year rule itself is a SECURE Act
    creation that doesn't apply to this death at all."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2019, death_year=2018, decedent_age_at_death=67,
        decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
        beneficiary_current_age=51,
    )
    assert result.depletion_deadline_year > 2100
    assert result.is_within_ten_year_window is True


def test_pre_secure_act_death_post_rbd_non_edb_uses_the_longer_of_divisor_unchanged():
    """Treas. Reg. 1.401(a)(9)-5's "longer of" rule predates the Act, so a
    post-RBD non-EDB's divisor is unaffected by a pre-2020 death_year --
    same mechanic as test_post_rbd_non_edb_uses_the_longer_of_beneficiary_
    or_owner_divisor above."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2019, death_year=2018, decedent_age_at_death=80,
        decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary",
        beneficiary_current_age=50,
    )
    assert result.divisor == 36.2  # Table I, age 50 -- the beneficiary's own, longer divisor


def test_pre_secure_act_death_pre_rbd_non_edb_takes_annual_stretch_not_zero():
    """The core rp-bdb behavior change: post-Act, a pre-RBD non-EDB owes
    $0 every year until the 10-year deadline forces full depletion
    (test_pre_rbd_non_edb_requires_no_annual_distribution above) -- but
    that "no annual RMD" carve-out is itself a SECURE Act creation. A
    pre-2020 death instead takes the classic annual stretch from year 1,
    using the beneficiary's own divisor alone."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2019, death_year=2018, decedent_age_at_death=67,
        decedent_was_taking_rmds=False, beneficiary_classification="non_eligible_designated_beneficiary",
        beneficiary_current_age=50,
    )
    assert result.required_amount == pytest.approx(1_000_000 / 36.2)
    assert result.divisor == 36.2  # Table I, age 50 -- beneficiary's own divisor, no "longer of" comparison
    assert result.table_used == "single_life_expectancy"


def test_pre_secure_act_death_pre_rbd_non_edb_divisor_decrements_by_one_each_year():
    kwargs = dict(
        inherited_balance=1_000_000, death_year=2018, decedent_age_at_death=67,
        decedent_was_taking_rmds=False, beneficiary_classification="non_eligible_designated_beneficiary",
    )
    year_1 = compute_inherited_rmd(tax_year=2019, beneficiary_current_age=50, **kwargs)
    year_2 = compute_inherited_rmd(tax_year=2020, beneficiary_current_age=51, **kwargs)
    assert year_1.divisor == 36.2
    assert year_2.divisor == 35.2  # 36.2 - 1.0, not a fresh age-51 lookup (35.3)


def test_secure_act_effective_year_boundary_death_year_2020_is_not_grandfathered():
    """death_year == 2020 (the Act's own effective year, not "before" it)
    still gets the post-Act treatment: $0 required and death_year + 10 as
    the default deadline, unlike test_pre_secure_act_death_pre_rbd_non_edb_
    takes_annual_stretch_not_zero's death_year=2018 case above."""
    result = compute_inherited_rmd(
        inherited_balance=1_000_000, tax_year=2024, death_year=2020, decedent_age_at_death=67,
        decedent_was_taking_rmds=False, beneficiary_classification="non_eligible_designated_beneficiary",
    )
    assert result.required_amount == 0.0
    assert result.depletion_deadline_year == 2030
