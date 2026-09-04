"""Comparison functions (FR-005–FR-011): thin loops over
run_plan_projection(), each varying exactly one dimension while holding
every other input — including the market return assumption — identical
across every candidate (FR-009). See
specs/004-strategy-comparison-layer/research.md and
contracts/comparison-api.md.

018-survivor-scenario-projection (rp-g8y, research.md Decision 6): the
mid-horizon death switch (filing status / Social Security / spending, see
projection.py's own module docstring and run_plan_projection()'s
docstring) needed NO change to this module — every function below already
forwards `household` unmodified into each candidate's own
run_plan_projection() call, so every candidate independently reflects the
identical switch a plain projection of that candidate would show
(tests/unit/comparison/test_compare.py's own coverage for this feature).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from retirement_planner.mechanics import AccountBalances, InheritedAccountBalance
from retirement_planner.scenario import Household, HsaContributionPlan

from .models import ComparisonResult, DeterministicReturnAssumption, StrategyConfiguration
from .projection import run_plan_projection

_MIN_CLAIMING_AGE = 62
_MAX_CLAIMING_AGE = 70


def _fresh_inherited_accounts(inherited_accounts: list[InheritedAccountBalance]) -> list[InheritedAccountBalance]:
    """012-inherited-ira-rmd (comparison-api.md): each candidate's own
    run_plan_projection() call mutates every InheritedAccountBalance's
    balance in place year by year -- a fresh, independently-copied list
    (and instances) must be built per candidate, never the same instances
    reused across candidates, or one candidate's projection would corrupt
    another's starting balance."""
    return [replace(account) for account in inherited_accounts]


def compare_roth_conversion_strategies(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    withdrawal_strategy: str,
    claiming_ages: dict[str, int],
    return_assumption: DeterministicReturnAssumption,
    candidates: list[StrategyConfiguration],
    hsa_contribution: HsaContributionPlan | None = None,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see _fresh_inherited_accounts()
    net_earned_income_against_spending: bool = False,
) -> ComparisonResult:
    """Runs run_plan_projection() once per candidate, forcing this call's
    shared withdrawal_strategy/claiming_ages/hsa_contribution onto every
    candidate so only the conversion dimension varies (FR-005, FR-009;
    hsa_contribution forced the same way per
    010-advanced-tax-benefits contracts/comparison-api.md). Each
    candidate's own conversion_window_mode/conversion_ceiling_mode/
    conversion_named_bracket_rate (rp-595) is left untouched by the
    replace() below -- these ARE the varying conversion dimension this
    function compares, the same way conversion_strategy/
    conversion_bracket_ceiling_or_amount/conversion_window already are.

    inherited_accounts (012-inherited-ira-rmd, comparison-api.md): forwarded
    to every candidate's run_plan_projection() call as its own fresh,
    independently-copied list (_fresh_inherited_accounts()) -- never the
    same instances shared across candidates. Defaults to [], reproducing
    every existing caller's exact prior behavior.

    net_earned_income_against_spending (rp-595): forced onto every
    candidate's run_plan_projection() call, the same way hsa_contribution
    already is -- a scenario-level setting, not a per-candidate varying
    dimension. Defaults to False, reproducing every existing caller's
    exact prior behavior.
    """
    projections = [
        run_plan_projection(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=replace(
                candidate,
                withdrawal_strategy=withdrawal_strategy,
                claiming_ages=claiming_ages,
                hsa_contribution=hsa_contribution,
            ),
            return_assumption=return_assumption,
            inherited_accounts=_fresh_inherited_accounts(inherited_accounts),
            net_earned_income_against_spending=net_earned_income_against_spending,
        )
        for candidate in candidates
    ]
    return ComparisonResult(
        dimension="roth_conversion_strategy",
        return_assumption=return_assumption,
        projections=projections,
    )


def compare_withdrawal_sequencing_strategies(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    conversion_window: tuple[int, int] | None,
    claiming_ages: dict[str, int],
    return_assumption: DeterministicReturnAssumption,
    candidates: list[StrategyConfiguration],
    hsa_contribution: HsaContributionPlan | None = None,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see _fresh_inherited_accounts()
    conversion_window_mode: Literal["explicit", "auto_gap_year"] = "explicit",
    conversion_ceiling_mode: Literal["dollar_amount", "named_bracket"] = "dollar_amount",
    conversion_named_bracket_rate: float | None = None,
    net_earned_income_against_spending: bool = False,
) -> ComparisonResult:
    """Runs run_plan_projection() once per candidate, forcing this call's
    shared conversion_strategy/conversion_bracket_ceiling_or_amount/
    conversion_window/claiming_ages/hsa_contribution onto every candidate
    so only the withdrawal-sequencing dimension varies (FR-006, FR-009;
    hsa_contribution forced the same way per
    010-advanced-tax-benefits contracts/comparison-api.md).

    inherited_accounts (012-inherited-ira-rmd): see
    compare_roth_conversion_strategies()'s own docstring -- identical
    per-candidate fresh-copy treatment. Defaults to [].

    conversion_window_mode/conversion_ceiling_mode/conversion_named_bracket_rate
    (rp-595): forced onto every candidate alongside conversion_strategy/
    conversion_bracket_ceiling_or_amount/conversion_window above -- the
    conversion dimension is held fixed here (withdrawal_strategy is what
    varies), so these three new fields are held fixed too, the same way.
    Defaults reproduce every existing caller's exact prior behavior.

    net_earned_income_against_spending (rp-595): forced onto every
    candidate's run_plan_projection() call, the same way hsa_contribution
    already is. Defaults to False, reproducing every existing caller's
    exact prior behavior.
    """
    projections = [
        run_plan_projection(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=replace(
                candidate,
                conversion_strategy=conversion_strategy,
                conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
                conversion_window=conversion_window,
                claiming_ages=claiming_ages,
                hsa_contribution=hsa_contribution,
                conversion_window_mode=conversion_window_mode,
                conversion_ceiling_mode=conversion_ceiling_mode,
                conversion_named_bracket_rate=conversion_named_bracket_rate,
            ),
            return_assumption=return_assumption,
            inherited_accounts=_fresh_inherited_accounts(inherited_accounts),
            net_earned_income_against_spending=net_earned_income_against_spending,
        )
        for candidate in candidates
    ]
    return ComparisonResult(
        dimension="withdrawal_sequencing",
        return_assumption=return_assumption,
        projections=projections,
    )


def compare_claiming_age_grid(
    household: Household,
    accounts: AccountBalances,
    traditional_ownership_shares: dict[str, float],
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    withdrawal_strategy: str,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    conversion_window: tuple[int, int] | None,
    return_assumption: DeterministicReturnAssumption,
    claiming_age_grid: list[dict[str, int]],
    hsa_contribution: HsaContributionPlan | None = None,
    inherited_accounts: list[InheritedAccountBalance] = [],  # noqa: B006 -- see _fresh_inherited_accounts()
    conversion_window_mode: Literal["explicit", "auto_gap_year"] = "explicit",
    conversion_ceiling_mode: Literal["dollar_amount", "named_bracket"] = "dollar_amount",
    conversion_named_bracket_rate: float | None = None,
    net_earned_income_against_spending: bool = False,
) -> ComparisonResult:
    """Runs run_plan_projection() once per grid entry, forcing this call's
    shared withdrawal_strategy/conversion_strategy/
    conversion_bracket_ceiling_or_amount/conversion_window/
    hsa_contribution onto every entry so only the claiming-age dimension
    varies (FR-008, FR-009; hsa_contribution forced the same way per
    010-advanced-tax-benefits contracts/comparison-api.md -- this
    function builds each StrategyConfiguration directly rather than
    starting from a caller-supplied candidate, so hsa_contribution needs
    an explicit parameter here, unlike the two compare_*() functions
    above that already take candidates: list[StrategyConfiguration]).
    Raises ValueError if any grid entry names a claiming age outside
    62-70 inclusive (FR-010), or omits any household member's own
    person_name (found via e2e testing rp-dd9 -- a candidate entry
    missing a member previously reached
    _household_gross_social_security_benefit()'s own
    claiming_ages[member.person_name] lookup as an uncaught KeyError,
    surfacing as a bare HTTP 500 rather than a clean, actionable error;
    routes/comparisons.py already maps a raised ValueError here to a 422,
    so raising here is enough -- no BFF-layer change needed).

    inherited_accounts (012-inherited-ira-rmd): see
    compare_roth_conversion_strategies()'s own docstring -- identical
    per-entry fresh-copy treatment. Defaults to [].

    conversion_window_mode/conversion_ceiling_mode/conversion_named_bracket_rate/
    net_earned_income_against_spending (rp-595): see
    compare_withdrawal_sequencing_strategies()'s own docstring -- same
    held-fixed-across-every-entry treatment. Defaults reproduce every
    existing caller's exact prior behavior.
    """
    member_names = {member.person_name for member in household.members}
    for entry in claiming_age_grid:
        if set(entry) != member_names:
            raise ValueError(
                f"claiming age grid entry {entry!r} must name exactly this household's members "
                f"{sorted(member_names)}"
            )
        for person_name, age in entry.items():
            if not (_MIN_CLAIMING_AGE <= age <= _MAX_CLAIMING_AGE):
                raise ValueError(
                    f"claiming age {age} for {person_name!r} is outside "
                    f"[{_MIN_CLAIMING_AGE}, {_MAX_CLAIMING_AGE}]"
                )

    projections = [
        run_plan_projection(
            household=household,
            accounts=accounts,
            traditional_ownership_shares=traditional_ownership_shares,
            annual_spending_need=annual_spending_need,
            state=state,
            reference_tax_year=reference_tax_year,
            start_plan_year=start_plan_year,
            start_tax_year=start_tax_year,
            plan_to_age=plan_to_age,
            strategy=StrategyConfiguration(
                label=f"claiming_ages_{index}",
                withdrawal_strategy=withdrawal_strategy,
                conversion_strategy=conversion_strategy,
                conversion_bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
                conversion_window=conversion_window,
                claiming_ages=claiming_ages_entry,
                hsa_contribution=hsa_contribution,
                conversion_window_mode=conversion_window_mode,
                conversion_ceiling_mode=conversion_ceiling_mode,
                conversion_named_bracket_rate=conversion_named_bracket_rate,
            ),
            return_assumption=return_assumption,
            inherited_accounts=_fresh_inherited_accounts(inherited_accounts),
            net_earned_income_against_spending=net_earned_income_against_spending,
        )
        for index, claiming_ages_entry in enumerate(claiming_age_grid)
    ]
    return ComparisonResult(
        dimension="claiming_age_grid",
        return_assumption=return_assumption,
        projections=projections,
    )
