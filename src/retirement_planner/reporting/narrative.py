"""Year-by-year plain-language narrative (rp-bm8.1, 028-results-walkthrough
FR-001-FR-011): builds a deterministic "story" per plan year for one
representative simulated path from a completed SimulationRun. Mirrors
aggregation.py's pure/testable style -- pure functions over already-computed
005/comparison output, no new tax, mechanics, or simulation computation
(FR-004/FR-014). See specs/028-results-walkthrough/research.md and
contracts/reporting-narrative-api.md.
"""

from __future__ import annotations

from retirement_planner.comparison import PlanProjection, PlanYearProjection, member_age_in_tax_year
from retirement_planner.mechanics import WITHDRAWAL_STRATEGIES, AccountType
from retirement_planner.scenario import Household
from retirement_planner.simulation import SimulationRun

from .aggregation import unverified_figure_names
from .models import NarrativeEntry, RunNarrative, YearStory

_TAX_CHANGE_THRESHOLD = 0.15
"""spec.md Clarifications (2026-09-03): >=15% year-over-year change in
combined federal+state taxes owed is "meaningfully large" (FR-003)."""

_ACCOUNT_TYPE_LABELS = {
    "taxable": "your taxable account",
    "traditional": "your Traditional account",
    "roth": "your Roth account",
}


def _format_currency(value: float) -> str:
    """Mirrors apps/streamlit_ui/src/rp_ui/formatting.py's format_currency()
    exactly, duplicated here rather than imported -- this core-library
    module must not depend on the Streamlit UI package."""
    return f"${value:,.2f}"


def select_representative_path(run: SimulationRun) -> int:
    """FR-001: the index into run.path_results whose PlanOutcome.ending_balance
    is numerically closest to run.percentile_bands[-1].percentiles[0.50] (the
    final plan year's median ending balance across every path). Ties broken
    by the lowest index (strict `<` below never replaces on an equal
    distance). When run.path_results has length 1, returns 0 without
    consulting percentile_bands at all (research.md §5)."""
    if len(run.path_results) == 1:
        return 0
    target = run.percentile_bands[-1].percentiles[0.50]
    best_index = 0
    best_distance: float | None = None
    for index, path in enumerate(run.path_results):
        distance = abs(path.outcome.ending_balance - target)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def _rmd_start_entries(year: PlanYearProjection, prior_year: PlanYearProjection | None) -> list[NarrativeEntry]:
    """FR-003: per member, member_rmd_amounts transitioning 0.0 -> nonzero
    (research.md §3). prior_year is None only for plan year 1, which is
    compared against a synthetic all-zero "starting state" (spec.md Edge
    Cases) -- so a household whose deemed owner is already RMD age in plan
    year 1 still gets a "began" entry rather than being silently skipped."""
    prior_rmds = prior_year.member_rmd_amounts if prior_year is not None else {}
    entries = []
    for person_name, amount in year.member_rmd_amounts.items():
        if amount > 0.0 and prior_rmds.get(person_name, 0.0) == 0.0:
            entries.append(
                NarrativeEntry(
                    driver_key="rmd_start",
                    label="Required Minimum Distributions began",
                    explanation=(
                        f"{person_name} began taking Required Minimum Distributions, adding "
                        f"{_format_currency(amount)} to taxable income."
                    ),
                    amounts={"rmd_amount": amount},
                )
            )
    return entries


def _ss_claiming_entries(year: PlanYearProjection, prior_year: PlanYearProjection | None) -> list[NarrativeEntry]:
    """FR-003: per member, member_social_security_benefits transitioning
    0.0 -> nonzero (already net of 025's earnings-test withholding,
    research.md §3)."""
    prior_benefits = prior_year.member_social_security_benefits if prior_year is not None else {}
    entries = []
    for person_name, amount in year.member_social_security_benefits.items():
        if amount > 0.0 and prior_benefits.get(person_name, 0.0) == 0.0:
            entries.append(
                NarrativeEntry(
                    driver_key="ss_claiming",
                    label="Social Security claimed",
                    explanation=(
                        f"{person_name} began receiving Social Security, {_format_currency(amount)} this year."
                    ),
                    amounts={"ss_benefit": amount},
                )
            )
    return entries


def _roth_conversion_entries(year: PlanYearProjection) -> list[NarrativeEntry]:
    """FR-003: mechanics.conversion.amount_converted > 0, every occurrence
    (not just the first -- research.md §3: the conversion amount can vary
    year to year under a bracket-fill strategy, and there is no separate
    "strategy started" event to detect since conversion_strategy is fixed
    for the whole run)."""
    amount_converted = year.mechanics.conversion.amount_converted
    if amount_converted <= 0.0:
        return []
    return [
        NarrativeEntry(
            driver_key="roth_conversion",
            label="Roth conversion",
            explanation=(
                f"A Roth conversion of {_format_currency(amount_converted)} added "
                f"{_format_currency(year.mechanics.conversion.ordinary_income_added)} to taxable income."
            ),
            amounts={
                "amount_converted": amount_converted,
                "ordinary_income_added": year.mechanics.conversion.ordinary_income_added,
            },
        )
    ]


def _withdrawal_source_change_entries(
    year: PlanYearProjection, prior_year: PlanYearProjection | None, withdrawal_order: tuple[AccountType, ...]
) -> list[NarrativeEntry]:
    """FR-003: per account_type in withdrawal_order, sequence_withdrawals
    transitioning 0.0 -> nonzero (a new source starts being tapped) or
    nonzero -> 0.0 (a source is exhausted) -- research.md §3. Cites
    WITHDRAWAL_STRATEGIES[strategy.withdrawal_strategy] (via the caller-
    supplied withdrawal_order) for the ordered source list, per the parent
    bead's design note."""
    prior_sequence = (
        {item.account_type: item.amount for item in prior_year.mechanics.withdrawal_plan.sequence_withdrawals}
        if prior_year is not None
        else {}
    )
    current_sequence = {item.account_type: item.amount for item in year.mechanics.withdrawal_plan.sequence_withdrawals}
    entries = []
    for account_type in withdrawal_order:
        prior_amount = prior_sequence.get(account_type, 0.0)
        current_amount = current_sequence.get(account_type, 0.0)
        label = _ACCOUNT_TYPE_LABELS.get(account_type, f"your {account_type} account")
        if prior_amount == 0.0 and current_amount > 0.0:
            entries.append(
                NarrativeEntry(
                    driver_key="withdrawal_source_change",
                    label="New withdrawal source tapped",
                    explanation=(
                        f"Withdrawals began drawing from {label}, {_format_currency(current_amount)} this year."
                    ),
                    amounts={"amount": current_amount},
                )
            )
        elif prior_amount > 0.0 and current_amount == 0.0:
            entries.append(
                NarrativeEntry(
                    driver_key="withdrawal_source_change",
                    label="Withdrawal source exhausted",
                    explanation=(
                        f"{label.capitalize()} stopped being drawn on this year "
                        f"(was {_format_currency(prior_amount)} the year before)."
                    ),
                    amounts={"prior_amount": prior_amount},
                )
            )
    return entries


def _tax_change_entries(year: PlanYearProjection, prior_year: PlanYearProjection | None) -> list[NarrativeEntry]:
    """FR-003: >=15% year-over-year change in federal_tax.federal_tax_owed +
    state_tax.state_tax_owed (spec.md Clarifications; research.md §3). When
    the prior combined tax is 0.0 (including plan year 1's synthetic
    zero-baseline, spec.md Edge Cases), any positive current tax crosses
    the threshold, avoiding a division by zero."""
    combined_tax = year.federal_tax.federal_tax_owed + year.state_tax.state_tax_owed
    prior_combined_tax = (
        prior_year.federal_tax.federal_tax_owed + prior_year.state_tax.state_tax_owed
        if prior_year is not None
        else 0.0
    )
    if prior_combined_tax == 0.0:
        crosses_threshold = combined_tax > 0.0
    else:
        crosses_threshold = abs(combined_tax - prior_combined_tax) / prior_combined_tax >= _TAX_CHANGE_THRESHOLD
    if not crosses_threshold:
        return []
    return [
        NarrativeEntry(
            driver_key="tax_change",
            label="Taxes owed changed significantly",
            explanation=(
                f"Total taxes owed changed from {_format_currency(prior_combined_tax)} to "
                f"{_format_currency(combined_tax)}."
            ),
            amounts={"prior_tax": prior_combined_tax, "current_tax": combined_tax},
        )
    ]


def _irmaa_entries(year: PlanYearProjection, prior_year: PlanYearProjection | None) -> list[NarrativeEntry]:
    """FR-003: irmaa.surcharge_owed transitioning 0.0 -> nonzero (start),
    and irmaa.income_basis differing from the prior year (lookback<->proxy
    switch) -- research.md §3. The basis switch has no sensible zero-
    substitute for plan year 1 (income_basis is categorical, not numeric),
    so it is only ever detected against a genuine prior year."""
    entries = []
    prior_surcharge = prior_year.irmaa.surcharge_owed if prior_year is not None else 0.0
    if year.irmaa.surcharge_owed > 0.0 and prior_surcharge == 0.0:
        entries.append(
            NarrativeEntry(
                driver_key="irmaa_start",
                label="IRMAA surcharge began",
                explanation=(
                    f"Medicare IRMAA surcharges of {_format_currency(year.irmaa.surcharge_owed)} began this year."
                ),
                amounts={"surcharge_owed": year.irmaa.surcharge_owed},
            )
        )
    if prior_year is not None and year.irmaa.income_basis != prior_year.irmaa.income_basis:
        entries.append(
            NarrativeEntry(
                driver_key="irmaa_basis_switch",
                label="IRMAA income basis switched",
                explanation=(
                    f"IRMAA's income basis switched from {prior_year.irmaa.income_basis.replace('_', ' ')} to "
                    f"{year.irmaa.income_basis.replace('_', ' ')}."
                ),
                amounts={},
            )
        )
    return entries


def _survivor_death_entries(
    year: PlanYearProjection, prior_year: PlanYearProjection | None, household: Household
) -> list[NarrativeEntry]:
    """FR-003: filing_status (018's effective, per-year field) transitioning
    "married_filing_jointly" -> "single" -- research.md §3. Plan year 1's
    "prior" filing status defaults to household.filing_status itself (spec.md
    Edge Cases), so a death configured to land in plan year 1 is still
    detected."""
    prior_filing_status = prior_year.filing_status if prior_year is not None else household.filing_status
    if (
        year.filing_status is not None
        and prior_filing_status == "married_filing_jointly"
        and year.filing_status == "single"
    ):
        return [
            NarrativeEntry(
                driver_key="survivor_death",
                label="Survivor filing status change",
                explanation=(
                    "Filing status changed to single following a modeled death; spending need adjusted to "
                    f"{_format_currency(year.effective_spending_need)}."
                ),
                amounts={"effective_spending_need": year.effective_spending_need},
            )
        ]
    return []


def _shortfall_entries(year: PlanYearProjection) -> list[NarrativeEntry]:
    """FR-003/spec.md Edge Cases: shortfall > 0.0, every occurrence -- not
    just the first, even in years after the plan has already gone into
    shortfall."""
    if year.shortfall <= 0.0:
        return []
    return [
        NarrativeEntry(
            driver_key="shortfall",
            label="Shortfall occurred",
            explanation=f"Spending needs exceeded available funds by {_format_currency(year.shortfall)} this year.",
            amounts={"shortfall": year.shortfall},
        )
    ]


_BASELINE_ENTRY = NarrativeEntry(
    driver_key="baseline",
    label="No notable change",
    explanation="No notable change from the prior year.",
    amounts={},
)
"""FR-005: the single fallback entry for a plan year where no other driver
fired -- never an empty entries list."""


def build_year_stories(projection: PlanProjection, household: Household, reference_tax_year: int) -> list[YearStory]:
    """FR-002/FR-003/FR-005: walks projection.years pairwise (plan year 1
    compared against a synthetic all-zero/starting-state "prior", spec.md
    Edge Cases) detecting the v1 driver set (research.md §3). Every plan
    year produces exactly one YearStory, with a single baseline
    NarrativeEntry when nothing else fired. Pure and deterministic:
    identical projection input -> byte-identical output every call
    (FR-006)."""
    withdrawal_order = WITHDRAWAL_STRATEGIES[projection.strategy.withdrawal_strategy]
    stories: list[YearStory] = []
    prior_year: PlanYearProjection | None = None
    for year in projection.years:
        entries: list[NarrativeEntry] = [
            *_rmd_start_entries(year, prior_year),
            *_ss_claiming_entries(year, prior_year),
            *_roth_conversion_entries(year),
            *_withdrawal_source_change_entries(year, prior_year, withdrawal_order),
            *_tax_change_entries(year, prior_year),
            *_irmaa_entries(year, prior_year),
            *_survivor_death_entries(year, prior_year, household),
            *_shortfall_entries(year),
        ]
        if not entries:
            entries = [_BASELINE_ENTRY]

        member_ages = {
            member.person_name: member_age_in_tax_year(member, year.tax_year, reference_tax_year)
            for member in household.members
        }

        stories.append(
            YearStory(
                plan_year=year.plan_year,
                tax_year=year.tax_year,
                member_ages=member_ages,
                entries=entries,
                # US3/FR-011 (research.md §4): this year's own unverified
                # figures, via the same derivation SummaryStatistics uses.
                unverified_figure_names=unverified_figure_names(year.figures_used),
            )
        )
        prior_year = year

    return stories


def build_narrative_for_run(run: SimulationRun, household: Household, reference_tax_year: int) -> RunNarrative:
    """Composes select_representative_path() + build_year_stories() over
    run.path_results[selected_path_index]. The single entry point BFF
    routes call -- computed once, for the selected path only (FR-008: no
    per-path computation, no new round trip)."""
    selected_path_index = select_representative_path(run)
    selected_path = run.path_results[selected_path_index]
    years = build_year_stories(selected_path, household, reference_tax_year)
    return RunNarrative(selected_path_index=selected_path_index, years=years)
