"""Plan-year orchestrator (FR-013, Edge Cases).

Ties RMD, withdrawal sequencing, and Roth conversion together for one plan
year: computes the withdrawal plan first (which treats rmd_amount as an
already-mandatory traditional draw), then computes the Roth conversion
against the *post-withdrawal* traditional and Roth balances — so RMD
dollars are structurally never also converted (research.md §6).

Implementation note: this function takes an explicit `rmd_figures_used`
parameter (default empty list) in addition to `rmd_amount`, which the
original contracts/mechanics-api.md draft omitted. PlanYearMechanicsResult's
documented `figures_used` field (data-model.md) is "the union of the RMD
figures used and conversion.figures_used" — but rmd_amount alone (a plain
float) carries no figure provenance, so this parameter was added during
implementation so a caller with a compute_rmd() RmdResult in hand can pass
its figures_used through. contracts/mechanics-api.md has been updated to
match.

See specs/003-retirement-account-mechanics/contracts/mechanics-api.md
("Operations (plan_year)" section) for the locked public shape.
"""

from __future__ import annotations

from retirement_planner.tax import FigureUsage, FilingStatus

from .models import AccountBalances, HsaContributionResult, PlanYearMechanicsResult
from .roth_conversion import compute_roth_conversion
from .withdrawal_sequencing import compute_withdrawal_plan


def compute_plan_year_mechanics(
    plan_year: int,
    tax_year: int,
    spending_need: float,
    starting_balances: AccountBalances,
    rmd_amount: float,
    social_security_gross_benefit: float,
    filing_status: FilingStatus,
    conversion_window: tuple[int, int] | None,
    conversion_strategy: str | None,
    conversion_bracket_ceiling_or_amount: float | None,
    withdrawal_strategy: str = "rmd_taxable_traditional_roth",
    rmd_figures_used: list[FigureUsage] | None = None,
    hsa_contribution: HsaContributionResult | None = None,
    inherited_distribution_amount: float = 0.0,
    inherited_rmd_figures_used: list[FigureUsage] | None = None,
    income_stream_total: float = 0.0,
    income_stream_figures_used: list[FigureUsage] | None = None,
    bracket_ceiling_figures_used: list[FigureUsage] | None = None,
) -> PlanYearMechanicsResult:
    """Orchestrates one plan year: calls compute_withdrawal_plan() first
    (rmd_amount is caller-supplied — typically the sum of one or more
    compute_rmd() calls, one per traditional-account-owning household
    member, since compute_rmd() is per-member while starting_balances is
    household-level), then, if conversion_window/conversion_strategy are
    not None, calls compute_roth_conversion() using the withdrawal plan's
    post-RMD ending traditional and Roth balances — never the
    pre-withdrawal balances — so RMD dollars are structurally excluded from
    conversion (FR-013). Returns a zeroed conversion field when no
    conversion plan is configured.

    hsa_contribution (010-advanced-tax-benefits FR-011): when provided,
    its amount_contributed reduces the returned ordinary_income by that
    same amount, and its figures_used are folded into the returned
    figures_used union. Optional, defaults to None (no HSA modeled —
    reproduces this function's exact prior behavior when omitted).

    inherited_distribution_amount/inherited_rmd_figures_used
    (012-inherited-ira-rmd, research.md §10): passed straight through to
    compute_withdrawal_plan() as its own new parameter of the same name;
    ordinary_income_established becomes rmd_drawn + traditional_draws +
    withdrawal_plan.inherited_distribution_drawn (was: the first two terms
    only). figures_used gains (inherited_rmd_figures_used or []) as a
    fourth unioned source. Both default such that omitting them reproduces
    this function's exact prior behavior unchanged.

    income_stream_total/income_stream_figures_used
    (021-pension-annuity-income, rp-pid, research.md §3): a caller-summed
    total across every configured pension/annuity/earned-income stream
    active this plan year (mechanics.income_streams.compute_income_stream_amount()),
    added into ordinary_income_established BEFORE compute_roth_conversion()
    runs -- unlike social_security_gross_benefit, which stays a separate,
    partially-excluded income component, this income is fully taxable
    ordinary income and must reduce that year's remaining bracket-fill
    headroom the same way a traditional withdrawal already does.
    figures_used gains (income_stream_figures_used or []) as a fifth
    unioned source. Both default such that omitting them reproduces this
    function's exact prior behavior unchanged.

    bracket_ceiling_figures_used (rp-595): when the caller resolved
    conversion_bracket_ceiling_or_amount itself via
    tax.bracket_ceiling_for_rate() (RothConversionPlan.ceiling_mode ==
    "named_bracket") rather than passing a scenario-authored dollar figure
    through unchanged, its own returned figures_used (which bracket table/
    standard-deduction schedule was actually consulted) is folded in here
    as a sixth unioned source -- so the resolved ceiling's provenance is
    auditable the same way every other figure this function touches
    already is. Defaults to None, reproducing this function's exact prior
    behavior when omitted (every caller not using named-bracket mode).
    """
    withdrawal_plan = compute_withdrawal_plan(
        spending_need=spending_need,
        rmd_amount=rmd_amount,
        starting_balances=starting_balances,
        strategy=withdrawal_strategy,
        inherited_distribution_amount=inherited_distribution_amount,
    )

    traditional_draws = sum(
        item.amount for item in withdrawal_plan.sequence_withdrawals if item.account_type == "traditional"
    )
    ordinary_income_established = (
        withdrawal_plan.rmd_drawn
        + traditional_draws
        + withdrawal_plan.inherited_distribution_drawn
        + income_stream_total
    )

    conversion = compute_roth_conversion(
        plan_year=plan_year,
        window=conversion_window,
        strategy=conversion_strategy,
        bracket_ceiling_or_amount=conversion_bracket_ceiling_or_amount,
        ordinary_income_established=ordinary_income_established,
        social_security_gross_benefit=social_security_gross_benefit,
        filing_status=filing_status,
        tax_year=tax_year,
        traditional_balance=withdrawal_plan.ending_balances.traditional,
        roth_balance=withdrawal_plan.ending_balances.roth,
    )

    ending_balances = AccountBalances(
        traditional=conversion.ending_traditional_balance,
        roth=conversion.ending_roth_balance,
        taxable=withdrawal_plan.ending_balances.taxable,
    )

    ordinary_income = ordinary_income_established + conversion.ordinary_income_added
    if hsa_contribution is not None:
        ordinary_income -= hsa_contribution.amount_contributed

    figures_used = [
        *(rmd_figures_used or []),
        *conversion.figures_used,
        *(hsa_contribution.figures_used if hsa_contribution is not None else []),
        *(inherited_rmd_figures_used or []),
        *(income_stream_figures_used or []),
        *(bracket_ceiling_figures_used or []),
    ]

    return PlanYearMechanicsResult(
        plan_year=plan_year,
        withdrawal_plan=withdrawal_plan,
        conversion=conversion,
        ending_balances=ending_balances,
        ordinary_income=ordinary_income,
        figures_used=figures_used,
    )
