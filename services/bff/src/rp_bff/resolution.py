"""Shared request-resolution helper (research.md §4, §6): scenario lookup,
blocking-flag check, StrategyConfiguration construction, reference-value
validation, and the cost-budget gate -- reused verbatim by User Story 3
(simulations), User Story 4 (comparisons), and User Story 5 (exports), the
same way 006's summarize_run() became the base every later function in
that feature reused. This module performs no tax/mechanics/simulation
computation of its own -- it only assembles already-validated inputs for
004/005 to consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from retirement_planner.comparison import StrategyConfiguration, deemed_rmd_owner
from retirement_planner.mechanics import (
    AccountBalances,
    CONVERSION_STRATEGIES,
    InheritedAccountBalance,
    WITHDRAWAL_STRATEGIES,
)
from retirement_planner.scenario import Household, Scenario, load_scenario
from retirement_planner.simulation import (
    SURVIVAL_TABLE,
    GenerationMode,
    ReturnPath,
    StressScenario,
    SurvivalCurve,
    apply_stress_scenario,
    generate_historical_bootstrap_paths,
    generate_return_paths,
)
from retirement_planner.tax import STATE_MODULES, UnsupportedTaxYearError

from .cost_estimation import check_cost_within_budget

DEFAULT_WITHDRAWAL_STRATEGY = "rmd_taxable_traditional_roth"


class BlockingValidationFlagsError(Exception):
    """Raised when the named scenario has at least one blocking
    ValidationFlag (FR-009) -- carries the blocking flags themselves so a
    route handler can report them without re-deriving anything."""

    def __init__(self, flags: list) -> None:
        """Carries the blocking flags themselves so a route handler can
        report them in the blocking_validation_flags response
        (contracts/bff-api.md) without re-deriving anything."""
        self.flags = flags
        super().__init__(f"scenario has {len(flags)} blocking validation flag(s)")


class UnknownReferenceValueError(Exception):
    """Raised when a request references a state/withdrawal-strategy/
    conversion-strategy not present in the current reference-data
    registries (FR-014, research.md §6)."""

    def __init__(self, field: str, value: str) -> None:
        """Carries which field and value were invalid, so a route handler
        can report both in the unknown_reference_value response
        (contracts/bff-api.md)."""
        self.field = field
        self.value = value
        super().__init__(f"unknown {field}: {value!r}")


def unsupported_tax_year_error(exc: UnsupportedTaxYearError) -> HTTPException:
    """Translates a raised UnsupportedTaxYearError (tax/models.py's own
    figure-lookup guard -- never falls back to the nearest documented
    year or extrapolates) into a 422 response, so a reference_tax_year/
    start_tax_year outside the documented range never reaches the client
    as a bare, unexplained 500. Found via a real run against the UI's
    unedited placeholder year (1900); reused by both
    routes/simulations.py and routes/comparisons.py since either
    reference_tax_year or start_tax_year can trigger this deep inside
    004/005's own computation, not during resolve_run_context()."""
    return HTTPException(
        status_code=422,
        detail={
            "error": "unsupported_tax_year",
            "figure_name": exc.figure_name,
            "requested_year": exc.requested_year,
            "documented_years": exc.available_years,
        },
    )


_SURVIVAL_CURVE_ROLES = ("primary", "spouse")
"""rp-9vl: simulation.SURVIVAL_TABLE provides exactly two illustrative
curves, keyed by role ("primary", "spouse") rather than person_name --
build_survival_curves() below maps them onto a resolved Household's own
members in order (index 0 -> "primary", index 1 -> "spouse"), mirroring
every existing test's own usage of SURVIVAL_TABLE (e.g.
tests/integration/test_simulation_lifecycle.py). Household.members has at
most 2 entries (scenario/models.py's own FR-013 invariant), so this never
runs out of roles."""


class SurvivalCurveAgeOutOfRangeError(Exception):
    """Raised by validate_survival_curve_coverage() when a household
    member's age, at some point in this run's own plan horizon, would fall
    outside SURVIVAL_TABLE's documented coverage (age 50-110 inclusive,
    survival_data.py) -- pre-flight, before run_simulation()/compare_*()
    would otherwise hit the same gap deep inside a per-path scoring loop as
    a bare, unhelpful KeyError(age) (rp-9vl). Carries which member and age
    so a route handler can report both, the same way
    UnsupportedTaxYearError's figure_name/requested_year already do."""

    def __init__(self, person_name: str, age: int) -> None:
        self.person_name = person_name
        self.age = age
        super().__init__(f"no survival curve coverage for {person_name!r} at age {age}")


def survival_curve_age_out_of_range_error(exc: SurvivalCurveAgeOutOfRangeError) -> HTTPException:
    """Translates a raised SurvivalCurveAgeOutOfRangeError into a 422
    response -- survival_adjusted scoring is opt-in (SimulationRequest/
    ComparisonRequest.survival_adjusted), so this is a request-shape
    problem (this household's ages don't fit the illustrative table this
    feature ships), never a bare 500."""
    return HTTPException(
        status_code=422,
        detail={
            "error": "survival_curve_age_out_of_range",
            "person_name": exc.person_name,
            "age": exc.age,
        },
    )


def build_survival_curves(household: Household) -> dict[str, SurvivalCurve]:
    """Maps SURVIVAL_TABLE's two illustrative roles onto household.members
    in order, keyed by each member's own person_name -- the shape
    run_simulation()/simulation.compare_*() require (rp-9vl,
    specs/005-simulation-engine/research.md §5)."""
    return {member.person_name: SURVIVAL_TABLE[role] for member, role in zip(household.members, _SURVIVAL_CURVE_ROLES)}


def validate_survival_curve_coverage(household: Household, survival_curves: dict[str, SurvivalCurve], plan_to_age: int, owner_current_age: int) -> None:
    """Pre-flight check for every age a completed run could ever look up in
    survival_curves (monte_carlo.run_simulation()'s own
    `member.current_age + (shortfall_year.tax_year - reference_tax_year)`
    formula): the earliest possible lookup is a member's own current_age
    (an immediate, plan-year-1 shortfall); the latest is that same age plus
    the full horizon (plan_to_age - owner_current_age, the same
    horizon_years derivation routes/simulations.py and routes/
    comparisons.py already use for generate_return_paths()). Raises
    SurvivalCurveAgeOutOfRangeError at the first age missing from that
    member's curve, rather than letting run_simulation() discover the same
    gap only after running every requested path (rp-9vl)."""
    max_horizon = plan_to_age - owner_current_age
    for member in household.members:
        curve = survival_curves[member.person_name]
        for age in range(member.current_age, member.current_age + max_horizon + 1):
            if age not in curve.probabilities_by_age:
                raise SurvivalCurveAgeOutOfRangeError(member.person_name, age)


@dataclass
class ResolvedRunContext:
    """Everything a single run/candidate needs, already validated and
    defaulted -- what 004/005's compute functions actually take as
    arguments."""

    scenario: Scenario
    household: Household
    accounts: AccountBalances
    traditional_ownership_shares: dict[str, float]
    inherited_accounts: list[InheritedAccountBalance]
    strategy: StrategyConfiguration
    state: str
    plan_to_age: int
    n_paths: int
    seed: int


def _sum_accounts(scenario: Scenario) -> AccountBalances:
    """Sums same-typed Account entries -- 001's Scenario schema allows more
    than one Account of a given type; 004/005's AccountBalances takes one
    total per type.

    012-inherited-ira-rmd (data-model.md § Exclusion from pooling): an
    inherited account is excluded entirely -- it is never legally
    commingled with the beneficiary's own accounts (research.md §5), and
    is instead tracked independently via _inherited_accounts() below."""
    totals = {"traditional": 0.0, "roth": 0.0, "taxable": 0.0}
    for account in scenario.accounts:
        if account.inherited is not None:
            continue
        totals[account.account_type] += account.balance
    return AccountBalances(traditional=totals["traditional"], roth=totals["roth"], taxable=totals["taxable"])


def _traditional_ownership_shares(scenario: Scenario) -> dict[str, float]:
    """011-per-owner-accounts: each household member's fixed share (0-1) of
    the scenario's initial pooled traditional balance (data-model.md §
    Derived) -- computed once per resolved run, from the same accounts list
    _sum_accounts() sums, alongside it. Callable only once the scenario has
    already been confirmed is_usable (checked immediately before this is
    called, below), so every account.owner here is guaranteed non-None and
    a real household member's person_name -- validate()'s own guarantee.

    012-inherited-ira-rmd: an inherited account is excluded from this
    pooled total too, for the same reason _sum_accounts() excludes it
    (data-model.md § Exclusion from pooling)."""
    per_member_traditional = {member.person_name: 0.0 for member in scenario.household.members}
    household_traditional_total = 0.0
    for account in scenario.accounts:
        if account.inherited is not None:
            continue
        if account.account_type == "traditional":
            per_member_traditional[account.owner] += account.balance
            household_traditional_total += account.balance
    if household_traditional_total <= 0:
        # Never zero-divide; the shares don't matter once the pooled total
        # is zero -- it can only ever stay zero (research.md §2), so every
        # member's RMD is $0 regardless of the value assigned here.
        return {person_name: 0.0 for person_name in per_member_traditional}
    return {person_name: balance / household_traditional_total for person_name, balance in per_member_traditional.items()}


_MINOR_CHILD_MAJORITY_AGE = 21
"""013-inherited-ira-edge-cases research.md §5: the IRS's own final-
regulation age of majority for the minor-child EDB -> 10-year-rule
transition (Pub. 590-B (2025) p.10's "attainment of majority") -- not a
state's own age-of-majority law."""

_SECURE_ACT_EFFECTIVE_YEAR = 2020
"""rp-bdb: the SECURE Act's 10-year rule (and the whole EDB/non-EDB
beneficiary-classification scheme it created) applies only to an owner who
died on or after this year -- Pub. L. 116-94 §401, effective for deaths on
or after 2020-01-01. Mirrors mechanics/inherited_rmd.py's own same-named,
same-value constant -- that module independently re-derives this same
death_year check for its own annual-RMD computation; this one governs only
whether a forced-depletion deadline exists at all."""

_NO_FORCED_DEPLETION_DEADLINE_YEARS = 200
"""013-inherited-ira-edge-cases research.md §6: added to death_year for a
true EDB (spouse, or non-spouse who is not a minor child) -- a sentinel
far beyond any plan_to_age this project can represent, standing in for
"no 10-year deadline at all" without changing
InheritedAccountBalance.depletion_deadline_year's type to int | None."""


def _inherited_accounts(scenario: Scenario, reference_tax_year: int) -> list[InheritedAccountBalance]:
    """012-inherited-ira-rmd (data-model.md § Derived), extended by
    013-inherited-ira-edge-cases (research.md §5, §6, § Handoff): one
    InheritedAccountBalance per Account with inherited is not None,
    independently tracked (never pooled -- research.md §5). Callable only
    once the scenario has already been confirmed is_usable, so every
    inherited account here is guaranteed account_type in
    ("traditional", "roth"), a non-trust/entity beneficiary, and a
    non-None account_id/owner -- validate()'s own guarantee (the two
    blocking rules in scenario-api.md, 013 research.md §8).

    depletion_deadline_year (013 research.md §5, §6; rp-bdb): death_year + 10
    for a non-eligible designated beneficiary (unchanged from 012);
    majority_year + 10 for a minor-child EDB, where majority_year is
    computed once here from the beneficiary's own current_age and
    reference_tax_year (the same age-anchoring arithmetic
    comparison/projection.py's own member_age_in_tax_year() uses); the
    "effectively never" sentinel for any other EDB -- and, since rp-bdb,
    for *any* classification when death_year predates the SECURE Act's
    2020 effective year, since the 10-year rule (and the whole EDB/
    non-EDB classification scheme itself) doesn't apply to that death at
    all -- it's grandfathered under the pre-Act stretch rules regardless
    of what beneficiary_classification the scenario recorded."""
    member_current_age = {member.person_name: member.current_age for member in scenario.household.members}
    result = []
    for account in scenario.accounts:
        if account.inherited is None:
            continue
        details = account.inherited
        is_edb = details.beneficiary_classification != "non_eligible_designated_beneficiary"
        is_minor_child = details.beneficiary_relationship == "minor_child" and details.beneficiary_classification == "eligible_designated_beneficiary_other"
        if details.death_year < _SECURE_ACT_EFFECTIVE_YEAR:
            # rp-bdb: grandfathered under the pre-Act stretch rules -- no
            # forced-depletion deadline at all, regardless of
            # beneficiary_classification (compute_inherited_rmd() itself
            # handles the pre-Act annual-RMD computation via this same
            # death_year check).
            depletion_deadline_year = details.death_year + _NO_FORCED_DEPLETION_DEADLINE_YEARS
        elif not is_edb:
            depletion_deadline_year = details.death_year + 10
        elif is_minor_child:
            birth_year = reference_tax_year - member_current_age[account.owner]
            majority_year = birth_year + _MINOR_CHILD_MAJORITY_AGE
            depletion_deadline_year = majority_year + 10
        else:
            depletion_deadline_year = details.death_year + _NO_FORCED_DEPLETION_DEADLINE_YEARS
        result.append(
            InheritedAccountBalance(
                account_id=account.account_id,
                balance=account.balance,
                death_year=details.death_year,
                decedent_age_at_death=details.decedent_age_at_death,
                depletion_deadline_year=depletion_deadline_year,
                account_type=account.account_type,
                decedent_was_taking_rmds=details.decedent_was_taking_rmds,
                beneficiary_classification=details.beneficiary_classification,
                beneficiary_person_name=account.owner,
            )
        )
    return result


def resolve_run_context(
    scenario_name: str,
    *,
    withdrawal_strategy: str | None,
    state: str | None,
    plan_to_age: int | None,
    n_paths: int | None,
    seed: int | None,
    reference_tax_year: int,
    scenarios_dir: Path | None = None,
) -> ResolvedRunContext:
    """Loads the named scenario (raises ScenarioParseError if it doesn't
    exist -- callers translate that to the "no_such_scenario" response
    shape, mirroring routes/scenarios.py's own handling), rejects it if it
    has blocking validation flags (FR-009), resolves optional fields from
    the scenario's own SimulationSettings when omitted (FR-011), validates
    state/withdrawal_strategy against the live reference-data registries
    (FR-014), and builds the StrategyConfiguration 004/005 need from the
    scenario's own household/roth_conversion data (data-model.md § Run
    Request/Response).

    reference_tax_year (013-inherited-ira-edge-cases): forwarded to
    _inherited_accounts() to compute a minor-child EDB's own
    majority-triggered depletion deadline (research.md §5) -- every
    existing caller already has this value in scope (each request body's
    own reference_tax_year), so this is a new required keyword-only
    parameter, not optional."""
    scenario = load_scenario(scenario_name, scenarios_dir=scenarios_dir)

    if not scenario.is_usable:
        blocking_flags = [flag for flag in scenario.validation_flags if flag.severity == "blocking"]
        raise BlockingValidationFlagsError(blocking_flags)

    resolved_withdrawal_strategy = withdrawal_strategy or DEFAULT_WITHDRAWAL_STRATEGY
    if resolved_withdrawal_strategy not in WITHDRAWAL_STRATEGIES:
        raise UnknownReferenceValueError("withdrawal_strategy", resolved_withdrawal_strategy)

    resolved_state = state or scenario.state
    if resolved_state not in STATE_MODULES:
        raise UnknownReferenceValueError("state", resolved_state)

    if scenario.roth_conversion is not None:
        if scenario.roth_conversion.strategy not in CONVERSION_STRATEGIES:
            raise UnknownReferenceValueError("conversion_strategy", scenario.roth_conversion.strategy)
        conversion_strategy = scenario.roth_conversion.strategy
        conversion_bracket_ceiling_or_amount = scenario.roth_conversion.bracket_ceiling_or_amount
        conversion_window = scenario.roth_conversion.window
    else:
        conversion_strategy = None
        conversion_bracket_ceiling_or_amount = None
        conversion_window = None

    strategy = StrategyConfiguration(
        label=scenario_name,
        withdrawal_strategy=resolved_withdrawal_strategy,
        conversion_strategy=conversion_strategy,
        conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
        conversion_window=conversion_window,
        claiming_ages={member.person_name: member.ss_claim_age for member in scenario.household.members},
        # 010-advanced-tax-benefits: resolved the same way roth_conversion
        # is, immediately above -- an opaque scenario-level block passed
        # through unvalidated beyond shape (001's own precedent).
        hsa_contribution=scenario.hsa_contribution,
    )

    return ResolvedRunContext(
        scenario=scenario,
        household=scenario.household,
        accounts=_sum_accounts(scenario),
        traditional_ownership_shares=_traditional_ownership_shares(scenario),
        inherited_accounts=_inherited_accounts(scenario, reference_tax_year),
        strategy=strategy,
        state=resolved_state,
        plan_to_age=plan_to_age if plan_to_age is not None else scenario.simulation_settings.plan_to_age,
        n_paths=n_paths if n_paths is not None else scenario.simulation_settings.n_paths,
        seed=seed if seed is not None else scenario.simulation_settings.seed,
    )


def check_run_cost(context: ResolvedRunContext, candidate_count: int = 1) -> None:
    """Wires estimate_cost_seconds()/check_cost_within_budget() into a
    resolved context -- rejects before any 004/005 call if the estimated
    cost exceeds the budget (FR-018)."""
    owner = deemed_rmd_owner(context.household)
    horizon_years = context.plan_to_age - owner.current_age + 1
    check_cost_within_budget(path_count=context.n_paths, candidate_count=candidate_count, horizon_years=horizon_years)


def generate_configured_return_paths(
    context: ResolvedRunContext,
    horizon_years: int,
    start_plan_year: int,
    generation_mode: GenerationMode,
    historical_block_length: int,
    stress_scenario: StressScenario | None,
) -> list[ReturnPath]:
    """Builds this run's return paths per generation_mode
    (026-advanced-simulation-options, research.md Decision 1) --
    generate_return_paths() for "parametric" (default, every existing
    caller's exact prior behavior), generate_historical_bootstrap_paths()
    for "historical_bootstrap" (rp-741, using historical_block_length) --
    then applies apply_stress_scenario() on top when stress_scenario is not
    None (rp-2bn), regardless of which generation_mode produced the
    underlying paths. Shared by resolve_and_run_simulation()
    (routes/simulations.py) and resolve_and_compare_simulated()
    (routes/comparisons.py) so both endpoints dispatch identically --
    mirrors build_survival_curves()'s own "one resolution.py helper, two
    callers" integration shape. Raises ValueError, propagated unchanged
    from whichever engine call raised it (a bad historical_block_length, or
    a stress window past horizon_last_plan_year) -- callers translate via
    invalid_simulation_options_error()."""
    if generation_mode == "historical_bootstrap":
        paths = generate_historical_bootstrap_paths(
            market_assumptions=context.scenario.market_assumptions,
            path_count=context.n_paths,
            horizon_years=horizon_years,
            start_plan_year=start_plan_year,
            seed=context.seed,
            block_length=historical_block_length,
        )
    else:
        paths = generate_return_paths(
            market_assumptions=context.scenario.market_assumptions,
            path_count=context.n_paths,
            horizon_years=horizon_years,
            start_plan_year=start_plan_year,
            seed=context.seed,
        )

    if stress_scenario is not None:
        paths = apply_stress_scenario(paths, stress=stress_scenario, horizon_last_plan_year=start_plan_year + horizon_years - 1)

    return paths


def invalid_simulation_options_error(exc: ValueError) -> HTTPException:
    """Translates a ValueError raised by generate_configured_return_paths()
    into a 422 response (026-advanced-simulation-options research.md
    Decision 5) -- mirrors survival_curve_age_out_of_range_error()'s own
    "dedicated translator per resolution-layer exception" shape. A plain
    str(exc) detail is enough here: generate_historical_bootstrap_paths()'s
    and apply_stress_scenario()'s own ValueError messages already name the
    specific problem in human-readable form, unlike
    SurvivalCurveAgeOutOfRangeError's case, which needed person_name/age
    broken out as separate fields for the UI to act on individually."""
    return HTTPException(status_code=422, detail={"error": "invalid_simulation_options", "detail": str(exc)})
