"""Integration test: the full quickstart.md walkthrough for
010-advanced-tax-benefits (IRMAA surcharge visibility, NIIT surtax
visibility, HSA contribution eligibility) — exercised through
run_plan_projection(), the same single per-plan-year loop
004-strategy-comparison-layer built and 005-simulation-engine already
reuses unchanged (plan.md's own Summary).

See specs/010-advanced-tax-benefits/quickstart.md — this test exercises
the same three sections. "FL" is used as the state throughout (a
zero-income-tax state, so every dollar of surcharge/surtax difference in
these tests is attributable to IRMAA/NIIT, never state tax).
"""

import pytest

from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances
from retirement_planner.scenario import Household, HouseholdMember, HsaContributionPlan

_STATE = "FL"
_RETURN_ASSUMPTION = DeterministicReturnAssumption(annual_real_return=0.0)  # isolates income-driven
    # effects (IRMAA/NIIT) from market-growth noise across plan years


def _household(you_age=66, spouse_age=64, you_hdhp_coverage=False, spouse_hdhp_coverage=False):
    return Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(
                person_name="you", current_age=you_age, ss_claim_age=67, ss_annual_benefit=32_000,
                hdhp_coverage=you_hdhp_coverage,
            ),
            HouseholdMember(
                person_name="spouse", current_age=spouse_age, ss_claim_age=67, ss_annual_benefit=24_000,
                hdhp_coverage=spouse_hdhp_coverage,
            ),
        ],
    )


def _strategy(**overrides):
    base = dict(
        label="test", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    base.update(overrides)
    return StrategyConfiguration(**base)


# -- User Story 1: IRMAA surcharge visibility --------------------------------


def test_us1_modest_income_household_has_no_irmaa_surcharge():
    """Acceptance Scenario US1.1."""
    household = _household()
    accounts = AccountBalances(traditional=200_000, roth=50_000, taxable=50_000)
    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=60_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=_strategy(), return_assumption=_RETURN_ASSUMPTION,
    )
    for year in projection.years:
        assert year.irmaa.surcharge_owed == 0.0
    assert projection.outcome.cumulative_irmaa_paid == 0.0


def test_us1_large_conversion_crosses_an_irmaa_tier_distinct_from_ordinary_tax():
    """Acceptance Scenario US1.2: the surcharge is a separately identifiable
    cost, not folded into cumulative_tax_paid."""
    household = _household()
    accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
    strategy = _strategy(
        conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=400_000,
        conversion_window=(2026, 2030),
    )
    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy, return_assumption=_RETURN_ASSUMPTION,
    )
    first_year = projection.years[0]
    assert first_year.irmaa.surcharge_owed > 0.0
    assert first_year.irmaa.tier_crossed is not None
    # Distinct from ordinary tax -- not folded into federal/state tax owed.
    assert first_year.irmaa.surcharge_owed not in (
        first_year.federal_tax.federal_tax_owed, first_year.state_tax.state_tax_owed,
    )
    assert projection.outcome.cumulative_irmaa_paid > 0.0
    assert projection.outcome.cumulative_irmaa_paid != projection.outcome.cumulative_tax_paid


def test_us1_surcharge_reflects_both_enrolled_members():
    """Acceptance Scenario US1.3: both members Medicare-enrolled (66, 64 ->
    wait, need both >= 65 for this specific case)."""
    household = _household(you_age=66, spouse_age=66)
    accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
    strategy = _strategy(
        conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=400_000,
        conversion_window=(2026, 2030),
    )
    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy, return_assumption=_RETURN_ASSUMPTION,
    )
    first_year = projection.years[0]
    assert first_year.irmaa.enrolled_member_count == 2


def test_us1_no_medicare_eligible_member_has_no_surcharge_regardless_of_income():
    """Acceptance Scenario US1.4, FR-004."""
    household = _household(you_age=60, spouse_age=58)
    accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
    strategy = _strategy(
        conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=400_000,
        conversion_window=(2026, 2030),
    )
    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=62,
        strategy=strategy, return_assumption=_RETURN_ASSUMPTION,
    )
    for year in projection.years:
        assert year.irmaa.surcharge_owed == 0.0
    assert projection.outcome.cumulative_irmaa_paid == 0.0


# -- User Story 2: NIIT surtax visibility -------------------------------------


def _run_conversion_heavy_projection(conversion_bracket_ceiling_or_amount: float):
    """A large Roth conversion pushes MAGI well past the NIIT threshold;
    the taxable-account withdrawals funding annual_spending_need supply a
    modest, separate investment_income figure -- used across several US2
    tests to isolate what the surtax does and doesn't scale with."""
    household = _household()
    accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
    strategy = _strategy(
        conversion_strategy="fill_to_bracket",
        conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
        conversion_window=(2026, 2030),
    )
    return run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy, return_assumption=_RETURN_ASSUMPTION,
    )


def test_us2_modest_income_household_has_no_niit_surtax():
    """Acceptance Scenario US2.1."""
    household = _household(you_age=60, spouse_age=58)
    accounts = AccountBalances(traditional=200_000, roth=50_000, taxable=50_000)
    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=60_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=62,
        strategy=_strategy(), return_assumption=_RETURN_ASSUMPTION,
    )
    for year in projection.years:
        assert year.niit.surtax_owed == 0.0
    assert projection.outcome.cumulative_niit_paid == 0.0


def test_us2_investment_income_above_threshold_shows_a_separately_identifiable_surtax():
    """Acceptance Scenario US2.2."""
    projection = _run_conversion_heavy_projection(400_000)
    first_year = projection.years[0]
    assert first_year.niit.threshold_exceeded is True
    assert first_year.niit.surtax_owed > 0.0
    assert first_year.niit.surtax_owed not in (
        first_year.federal_tax.federal_tax_owed, first_year.state_tax.state_tax_owed, first_year.irmaa.surcharge_owed,
    )
    assert projection.outcome.cumulative_niit_paid > 0.0


def test_us2_conversion_size_does_not_itself_scale_the_surtax():
    """Acceptance Scenario US2.3: the conversion amount only affects
    *whether* the threshold is crossed, never the surtax amount itself --
    confirmed by two scenarios with very different conversion sizes (both
    already well past the threshold) producing the identical surtax,
    since investment_income (from taxable-account spending withdrawals,
    unaffected by the conversion) is unchanged between them."""
    smaller_conversion = _run_conversion_heavy_projection(400_000)
    larger_conversion = _run_conversion_heavy_projection(600_000)

    first_year_smaller = smaller_conversion.years[0]
    first_year_larger = larger_conversion.years[0]

    assert first_year_larger.mechanics.ordinary_income > first_year_smaller.mechanics.ordinary_income
    assert first_year_larger.niit.investment_income == first_year_smaller.niit.investment_income
    assert first_year_larger.niit.surtax_owed == first_year_smaller.niit.surtax_owed


# -- User Story 3: HSA contribution eligibility -------------------------------


def _hsa_household_kwargs(hsa_contribution):
    """you starts at 64 (not yet Medicare-eligible) and crosses 65 partway
    through a 5-year horizon; spouse (50, also HDHP-covered) never crosses
    65 within it -- isolates the eligibility transition from any age-based
    IRMAA/NIIT interaction (spending/accounts kept modest, no conversion,
    so MAGI never approaches either threshold)."""
    household = _household(you_age=64, spouse_age=50, you_hdhp_coverage=True, spouse_hdhp_coverage=True)
    accounts = AccountBalances(traditional=200_000, roth=50_000, taxable=50_000)
    strategy = _strategy(hsa_contribution=hsa_contribution)
    return dict(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=60_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy, return_assumption=_RETURN_ASSUMPTION,
    )


def test_us3_both_members_eligible_before_older_members_enrollment():
    """Acceptance Scenario US3.1."""
    projection = run_plan_projection(**_hsa_household_kwargs(HsaContributionPlan(annual_amount=3_000.0)))
    first_year = projection.years[0]  # you=64, spouse=50
    by_name = {e.person_name: e for e in first_year.hsa_contribution.eligible_members}
    assert by_name["you"].eligible is True
    assert by_name["spouse"].eligible is True
    assert first_year.hsa_contribution.amount_contributed == 3_000.0


def test_us3_older_members_eligibility_ends_at_enrollment():
    """Acceptance Scenario US3.2."""
    projection = run_plan_projection(**_hsa_household_kwargs(HsaContributionPlan(annual_amount=3_000.0)))
    later_year = next(year for year in projection.years if year.plan_year == 2)  # you=65
    by_name = {e.person_name: e for e in later_year.hsa_contribution.eligible_members}
    assert by_name["you"].eligible is False
    assert "medicare" in by_name["you"].reason.lower()


def test_us3_younger_spouses_eligibility_is_unaffected_by_older_members_enrollment():
    """Acceptance Scenario US3.3, FR-010."""
    projection = run_plan_projection(**_hsa_household_kwargs(HsaContributionPlan(annual_amount=3_000.0)))
    later_year = next(year for year in projection.years if year.plan_year == 2)  # you=65, spouse=51
    by_name = {e.person_name: e for e in later_year.hsa_contribution.eligible_members}
    assert by_name["spouse"].eligible is True
    # Contribution still fully modeled (spouse alone -> self-only limit >= 3,000).
    assert later_year.hsa_contribution.amount_contributed == 3_000.0


def test_us3_contribution_reduces_ordinary_income_in_every_eligible_year():
    """Acceptance Scenario US3.4.

    Checked precisely for plan_year 1 only, where both runs still share
    an identical starting traditional balance. From plan_year 2 onward
    the two runs' balances have already diverged: the with-HSA run owed
    less tax in year 1, so less was withdrawn to fund it, leaving a
    larger traditional balance -- and therefore a larger RMD -- carried
    into year 2. That's a real, correct multi-year compounding effect of
    this engine (paying less tax now leaves more invested, which raises
    future RMDs), not something this test should assert away; the
    year-2-onward check below only confirms the reduction stays real
    (nonzero) and every eligible year's contribution is still reflected
    somewhere in ordinary_income, not that it's exactly 3,000 every year.
    """
    with_hsa = run_plan_projection(**_hsa_household_kwargs(HsaContributionPlan(annual_amount=3_000.0)))
    without_hsa = run_plan_projection(**_hsa_household_kwargs(None))

    first_with, first_without = with_hsa.years[0], without_hsa.years[0]
    assert first_with.mechanics.ordinary_income == pytest.approx(
        first_without.mechanics.ordinary_income - first_with.hsa_contribution.amount_contributed
    )

    for with_year, without_year in zip(with_hsa.years[1:], without_hsa.years[1:]):
        if with_year.hsa_contribution.amount_contributed > 0.0:
            assert with_year.mechanics.ordinary_income < without_year.mechanics.ordinary_income


# -- Polish: every new figure defaults verified=False and propagates (T032) --


def test_irmaa_niit_hsa_figures_are_all_unverified_and_propagate():
    """Principle III (Auditability): every new externally-sourced figure
    this feature introduces starts verified=False, and that status must
    reach unverified_figure_names, the same "needs verification"
    propagation path every existing tax figure already uses -- IRMAA/NIIT
    are computed every plan year regardless of whether a surcharge/surtax
    is actually triggered, and HSA eligibility/limits are computed every
    plan year regardless of whether a contribution is configured, so all
    four figure names are expected on every projection, not only ones
    that happen to trigger a nonzero result."""
    from retirement_planner.reporting import summarize_run
    from retirement_planner.simulation import run_simulation

    household = _household(you_age=66, spouse_age=64, you_hdhp_coverage=True)
    accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
    strategy = _strategy(hsa_contribution=HsaContributionPlan(annual_amount=1_000.0))

    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy, return_assumption=_RETURN_ASSUMPTION,
    )
    figure_names = {figure.name for year in projection.years for figure in year.figures_used}
    assert "irmaa_tiers_mfj" in figure_names
    assert "niit_threshold_mfj" in figure_names
    assert "niit_rate" in figure_names
    assert "hsa_contribution_limits" in figure_names
    assert all(not figure.verified for year in projection.years for figure in year.figures_used)

    # Same propagation through 006's own aggregation, the layer 007/008
    # actually surface unverified_figure_names through to a user.
    from retirement_planner.simulation import ReturnPath

    run = run_simulation(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state=_STATE,
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=68,
        strategy=strategy,
        return_paths=[ReturnPath(start_plan_year=1, annual_returns=[0.0, 0.0, 0.0], generation_mode="parametric")],
        candidate_label="test",
    )
    summary = summarize_run(run, household=household, reference_tax_year=2026)
    for name in ("irmaa_tiers_mfj", "niit_threshold_mfj", "niit_rate", "hsa_contribution_limits"):
        assert name in summary.unverified_figure_names


# -- Polish: the full quickstart.md walkthrough, chained verbatim (T035) --


def test_polish_010_full_quickstart_walkthrough():
    """All three sections of quickstart.md, using its own literal example
    code (not the shared _household()/_strategy() helpers above), so this
    test validates the document itself, not just the underlying engine."""
    from retirement_planner.mechanics.hsa import compute_hsa_contribution, compute_hsa_eligibility

    # -- §1: See the IRMAA surcharge a strategy triggers --
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="you", current_age=66, ss_claim_age=67, ss_annual_benefit=32_000),
            HouseholdMember(
                person_name="spouse", current_age=64, ss_claim_age=67, ss_annual_benefit=24_000,
                hdhp_coverage=True,
            ),
        ],
    )
    accounts = AccountBalances(traditional=1_800_000, roth=400_000, taxable=300_000)
    strategy = StrategyConfiguration(
        label="large_conversion", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy="fill_to_bracket", conversion_bracket_ceiling_or_amount=400_000,
        conversion_window=(2026, 2030), claiming_ages={"you": 67, "spouse": 67},
    )
    projection = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=110_000, state="FL",
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
        strategy=strategy, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    )
    first_year = projection.years[0]
    assert first_year.irmaa.tier_crossed is not None
    assert first_year.irmaa.surcharge_owed > 0.0
    assert first_year.irmaa.surcharge_owed != first_year.federal_tax.federal_tax_owed
    assert first_year.irmaa.surcharge_owed != first_year.state_tax.state_tax_owed

    # -- §2: See the NIIT surtax investment income triggers --
    strategy_niit = StrategyConfiguration(
        label="taxable_heavy", withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None, conversion_bracket_ceiling_or_amount=None, conversion_window=None,
        claiming_ages={"you": 67, "spouse": 67},
    )
    projection_niit = run_plan_projection(
        household=household, accounts=accounts, traditional_ownership_shares={"you": 0.75, "spouse": 0.25}, annual_spending_need=180_000, state="FL",
        reference_tax_year=2026, start_plan_year=1, start_tax_year=2026, plan_to_age=95,
        strategy=strategy_niit, return_assumption=DeterministicReturnAssumption(annual_real_return=0.04),
    )
    year = projection_niit.years[0]
    if year.niit.threshold_exceeded:
        assert year.niit.surtax_owed <= year.niit.investment_income * 0.038 + 1e-6

    # -- §3: See HSA eligibility survive one spouse's Medicare enrollment --
    eligibility = compute_hsa_eligibility(
        members=[("you", 66, False), ("spouse", 64, True)],
        medicare_enrolled={"you": True, "spouse": False},
    )
    result = compute_hsa_contribution(eligibility, configured_annual_amount=8_000, tax_year=2026)
    by_name = {e.person_name: e.eligible for e in result.eligible_members}
    assert by_name["you"] is False
    assert by_name["spouse"] is True
    assert result.amount_contributed > 0.0
