"""Unit tests for retirement_planner.reporting.narrative: select_representative_path()
(US1/US2), build_year_stories()'s per-driver detection (US1), reproducibility
(US2), and per-year unverified-figure scoping (US3). Mirrors
test_aggregation.py's fixture style -- real PlanProjection objects built via
run_plan_projection() with household/strategy/balance combinations tuned to
trigger exactly one driver's transition, then (for path-selection tests)
assembled into SimulationRun objects directly.
"""

from datetime import date

from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances
from retirement_planner.reporting import build_narrative_for_run, build_year_stories, select_representative_path
from retirement_planner.reporting.aggregation import unverified_figure_names
from retirement_planner.scenario import Household, HouseholdMember
from retirement_planner.simulation import PercentileBand, SimulationRun
from retirement_planner.tax import FigureUsage

_RETURN_0PCT = DeterministicReturnAssumption(annual_real_return=0.0)


def _strategy(**overrides):
    base = dict(
        label="test",
        withdrawal_strategy="rmd_taxable_traditional_roth",
        conversion_strategy=None,
        conversion_bracket_ceiling_or_amount=None,
        conversion_window=None,
        claiming_ages={},
    )
    base.update(overrides)
    return StrategyConfiguration(**base)


def _project(household, accounts, strategy, spending_need=20_000, plan_to_age=76, ownership=None, state="FL"):
    owner_shares = ownership or {member.person_name: 1.0 / len(household.members) for member in household.members}
    return run_plan_projection(
        household=household,
        accounts=accounts,
        traditional_ownership_shares=owner_shares,
        annual_spending_need=spending_need,
        state=state,
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=plan_to_age,
        strategy=strategy,
        return_assumption=_RETURN_0PCT,
    )


# --- select_representative_path() (US1/US2) ---


def _run(path_results, percentile_bands):
    return SimulationRun(
        candidate_label="test",
        strategy=_strategy(claiming_ages={"you": 99}),
        state="FL",
        path_results=path_results,
        success_rate=1.0,
        percentile_bands=percentile_bands,
        survival_adjusted_success_rate=None,
        figures_used=[],
    )


def _household_one():
    return Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=75, ss_claim_age=99, ss_annual_benefit=0)],
    )


def test_select_representative_path_single_path_returns_zero_without_percentile_bands():
    household = _household_one()
    projection = _project(household, AccountBalances(traditional=100_000, roth=0, taxable=0), _strategy(claiming_ages={"you": 99}))
    run = _run([projection], percentile_bands=[])

    assert select_representative_path(run) == 0


def test_select_representative_path_picks_the_path_closest_to_the_median():
    household = _household_one()
    strategy = _strategy(claiming_ages={"you": 99})
    low = _project(household, AccountBalances(traditional=100_000, roth=0, taxable=0), strategy)
    mid = _project(household, AccountBalances(traditional=500_000, roth=0, taxable=0), strategy)
    high = _project(household, AccountBalances(traditional=2_000_000, roth=0, taxable=0), strategy)
    median_ending_balance = mid.outcome.ending_balance
    bands = [PercentileBand(plan_year=1, percentiles={0.50: median_ending_balance})]
    run = _run([low, high, mid], percentile_bands=bands)  # mid deliberately last -> index 2

    assert select_representative_path(run) == 2


def test_select_representative_path_ties_break_to_the_lower_index():
    household = _household_one()
    strategy = _strategy(claiming_ages={"you": 99})
    projection = _project(household, AccountBalances(traditional=500_000, roth=0, taxable=0), strategy)
    # Two identical paths -> equal distance from the median either way.
    bands = [PercentileBand(plan_year=1, percentiles={0.50: projection.outcome.ending_balance})]
    run = _run([projection, projection], percentile_bands=bands)

    assert select_representative_path(run) == 0


# --- build_year_stories(): one fixture per v1 driver (US1) ---


def test_rmd_start_fires_once_on_the_transition_year_and_baseline_fires_after():
    """RMD 0 -> nonzero at plan_year 2 (age 73); plan years 4-6 are pure
    baseline once RMD/tax/withdrawal-source have all stabilized."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=72, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=0), strategy, plan_to_age=77)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    rmd_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "rmd_start"]
    assert rmd_years == [2]
    baseline_years = [s.plan_year for s in stories if [e.driver_key for e in s.entries] == ["baseline"]]
    assert baseline_years == [4, 5, 6]


def test_ss_claiming_fires_once_on_the_claiming_year():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=64, ss_claim_age=65, ss_annual_benefit=18_000)],
    )
    strategy = _strategy(claiming_ages={"Alex": 65})
    projection = _project(household, AccountBalances(traditional=0, roth=0, taxable=500_000), strategy, plan_to_age=68)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    ss_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "ss_claiming"]
    assert ss_years == [2]


def test_roth_conversion_fires_only_in_its_configured_window_year():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=60, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(
        claiming_ages={"Alex": 99},
        conversion_strategy="fixed_amount",
        conversion_bracket_ceiling_or_amount=10_000,
        conversion_window=(2027, 2027),
    )
    projection = _project(household, AccountBalances(traditional=200_000, roth=0, taxable=500_000), strategy, plan_to_age=63)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    conversion_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "roth_conversion"]
    assert conversion_years == [2]


def test_withdrawal_source_change_fires_when_a_source_is_exhausted():
    """A small taxable balance ($15k) against $20k/yr spending is drained
    by the end of plan year 1 (already blended with a traditional draw
    that same year) -- plan year 1 has no real prior year, so both
    taxable and traditional fire as "started" against the synthetic
    zero-baseline (spec.md Edge Cases). Plan year 2 draws from traditional
    only, so taxable's 15000 -> 0 "exhausted" transition is detected
    there."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=60, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=500_000, roth=0, taxable=15_000), strategy, plan_to_age=63)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    change_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "withdrawal_source_change"]
    assert change_years == [1, 1, 2]


def test_irmaa_start_and_basis_switch_fire_on_their_own_transition_years():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=72, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=4_000_000, roth=0, taxable=0), strategy, plan_to_age=74)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    start_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "irmaa_start"]
    switch_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "irmaa_basis_switch"]
    assert start_years == [2]
    assert switch_years == [3]


def test_survivor_death_fires_on_the_post_death_plan_year():
    household = Household(
        filing_status="married_filing_jointly",
        members=[
            HouseholdMember(person_name="Alex", current_age=70, ss_claim_age=99, ss_annual_benefit=0, predicted_death_age=72),
            HouseholdMember(person_name="Sam", current_age=68, ss_claim_age=99, ss_annual_benefit=0),
        ],
        survivor_spending_reduction_pct=0.3,
    )
    strategy = _strategy(claiming_ages={"Alex": 99, "Sam": 99})
    projection = _project(
        household,
        AccountBalances(traditional=0, roth=0, taxable=500_000),
        strategy,
        plan_to_age=74,
        ownership={"Alex": 0.5, "Sam": 0.5},
    )

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    death_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "survivor_death"]
    assert death_years == [4]


def test_shortfall_fires_on_every_occurrence_not_just_the_first():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=75, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=10_000, roth=0, taxable=0), strategy, spending_need=500_000, plan_to_age=77)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    shortfall_years = [s.plan_year for s in stories for e in s.entries if e.driver_key == "shortfall"]
    assert shortfall_years == [1, 2, 3]


def test_every_year_has_at_least_one_entry():
    """FR-005: never an empty entries list, whether or not a real driver fired."""
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=72, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=0), strategy, plan_to_age=77)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    assert all(len(story.entries) >= 1 for story in stories)


def test_covers_every_plan_year_with_no_gaps_or_duplicates():
    household = _household_one()
    strategy = _strategy(claiming_ages={"you": 99})
    projection = _project(household, AccountBalances(traditional=500_000, roth=0, taxable=0), strategy, plan_to_age=80)

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    assert [s.plan_year for s in stories] == [year.plan_year for year in projection.years]


# --- Reproducibility (US2, FR-006/SC-002) ---


def test_build_narrative_for_run_is_byte_identical_across_repeated_calls():
    household = Household(
        filing_status="single",
        members=[HouseholdMember(person_name="Alex", current_age=72, ss_claim_age=99, ss_annual_benefit=0)],
    )
    strategy = _strategy(claiming_ages={"Alex": 99})
    projection = _project(household, AccountBalances(traditional=700_000, roth=0, taxable=0), strategy, plan_to_age=77)
    bands = [PercentileBand(plan_year=1, percentiles={0.50: projection.outcome.ending_balance})]
    run = _run([projection], percentile_bands=bands)

    first = build_narrative_for_run(run, household=household, reference_tax_year=2026)
    second = build_narrative_for_run(run, household=household, reference_tax_year=2026)

    assert first.selected_path_index == second.selected_path_index
    assert first.years == second.years


# --- Per-year unverified-figure scoping (US3, FR-011) ---


def _figure(name, verified):
    return FigureUsage(name=name, citation="test", last_verified=date(2026, 1, 1), verified=verified)


def test_unverified_figure_names_reflects_that_years_own_figures_used():
    household = _household_one()
    strategy = _strategy(claiming_ages={"you": 99})
    projection = _project(household, AccountBalances(traditional=500_000, roth=0, taxable=0), strategy, plan_to_age=77)
    projection.years[1].figures_used.append(_figure("test_unverified_figure", False))

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    assert stories[1].unverified_figure_names == ["test_unverified_figure"]
    assert stories[0].unverified_figure_names == []


def test_unverified_figure_names_matches_the_shared_aggregation_helper():
    household = _household_one()
    strategy = _strategy(claiming_ages={"you": 99})
    projection = _project(household, AccountBalances(traditional=500_000, roth=0, taxable=0), strategy, plan_to_age=77)
    projection.years[0].figures_used.append(_figure("dupe", False))
    projection.years[0].figures_used.append(_figure("dupe", False))

    stories = build_year_stories(projection, household, reference_tax_year=2026)

    assert stories[0].unverified_figure_names == unverified_figure_names(projection.years[0].figures_used)
    assert stories[0].unverified_figure_names == ["dupe"]
