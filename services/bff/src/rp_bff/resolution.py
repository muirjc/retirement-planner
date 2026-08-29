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
    return {
        person_name: balance / household_traditional_total
        for person_name, balance in per_member_traditional.items()
    }


def _inherited_accounts(scenario: Scenario) -> list[InheritedAccountBalance]:
    """012-inherited-ira-rmd (data-model.md § Derived): one
    InheritedAccountBalance per Account with inherited is not None,
    independently tracked (never pooled -- research.md §5). Callable only
    once the scenario has already been confirmed is_usable, so every
    inherited account here is guaranteed account_type="traditional",
    inherited.decedent_was_taking_rmds=True,
    inherited.beneficiary_classification="non_eligible_designated_beneficiary",
    and a non-None account_id -- validate()'s own guarantee (the four
    blocking rules in scenario-api.md)."""
    return [
        InheritedAccountBalance(
            account_id=account.account_id,
            balance=account.balance,
            death_year=account.inherited.death_year,
            decedent_age_at_death=account.inherited.decedent_age_at_death,
            depletion_deadline_year=account.inherited.death_year + 10,
        )
        for account in scenario.accounts
        if account.inherited is not None
    ]


def resolve_run_context(
    scenario_name: str,
    *,
    withdrawal_strategy: str | None,
    state: str | None,
    plan_to_age: int | None,
    n_paths: int | None,
    seed: int | None,
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
    Request/Response)."""
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
        inherited_accounts=_inherited_accounts(scenario),
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
    check_cost_within_budget(
        path_count=context.n_paths, candidate_count=candidate_count, horizon_years=horizon_years
    )
