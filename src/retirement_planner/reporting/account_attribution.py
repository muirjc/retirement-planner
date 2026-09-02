"""Per-account year-by-year attribution (015-per-account-projection-detail,
FR-001-FR-006). Turns an already-completed PlanProjection's pooled,
per-account-*type* figures into per-*account* rows, using a fixed share
computed once from the scenario's starting per-account balances --
extending 011-per-owner-accounts' own already-shipped precedent (a fixed
share, computed once, applied to whatever the pooled engine already
produces) down from the member level to the individual account level,
rather than rearchitecting the engine's pooled AccountBalances arithmetic
(research.md §1).

Pure functions over already-computed 001/004 output -- no new tax,
mechanics, comparison, or simulation computation, mirroring
aggregation.py's own FR-014 discipline. See research.md and
contracts/reporting-api.md for the full field-by-field derivation and the
exact-vs-attributed inventory (data-model.md § AccountYearDetail).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from retirement_planner.comparison import PlanProjection
from retirement_planner.scenario import Account

AccountType = Literal["traditional", "roth", "taxable"]
Attribution = Literal["independently_tracked", "fixed_share_of_pooled_total"]


@dataclass
class AccountShare:
    """data-model.md § AccountShare. One entry per account the scenario
    configures, ordinary and inherited alike -- an inherited account's own
    fixed_share is always 1.0 (never apportioned; its year-by-year state
    is exact by construction, research.md §3) and exists here only to
    carry its account_type/owner alongside its ordinary siblings, so
    attribute_plan_projection() has one uniform account list to walk."""

    account_id: str
    account_type: AccountType
    owner: str
    inherited: bool
    fixed_share: float
    """For an ordinary account: account.balance / sum(balances of every
    non-inherited account of the same type in the household), at
    scenario-entry time. 0.0 when that type's household total is <= 0
    (research.md §2's zero-guard, mirroring
    services/bff/src/rp_bff/resolution.py's
    _traditional_ownership_shares()) -- never a ZeroDivisionError. Always
    1.0 for an inherited account (not used for apportionment there)."""


@dataclass
class AccountYearDetail:
    """data-model.md § AccountYearDetail."""

    account_id: str
    account_type: AccountType
    owner: str
    starting_balance: float
    ending_balance: float
    rmd_amount: float
    withdrawal_amount: float
    attribution: Attribution


@dataclass
class PlanYearAccountDetail:
    """data-model.md § PlanYearAccountDetail."""

    plan_year: int
    tax_year: int
    accounts: list[AccountYearDetail] = field(default_factory=list)
    member_social_security_benefits: dict[str, float] = field(default_factory=dict)
    member_income_stream_amounts: dict[str, float] = field(default_factory=dict)
    """021-pension-annuity-income (rp-pid): mirrors
    member_social_security_benefits, copied from the corresponding
    comparison.PlanYearProjection."""


def compute_account_shares(accounts: list[Account]) -> list[AccountShare]:
    """One AccountShare per account the scenario configures (research.md
    §2, §3) -- ordinary and inherited alike. Pure function of accounts'
    starting balances -- no randomness, no I/O. Called once per request
    (BFF layer), not once per candidate/path, since it depends only on
    the scenario's own accounts list."""
    ordinary = [account for account in accounts if account.inherited is None]

    type_totals: dict[AccountType, float] = {"traditional": 0.0, "roth": 0.0, "taxable": 0.0}
    for account in ordinary:
        type_totals[account.account_type] += account.balance

    shares = []
    for account in accounts:
        if account.inherited is not None:
            # Never apportioned -- exact by construction (research.md §3).
            fixed_share = 1.0
        else:
            pool = type_totals[account.account_type]
            # Never zero-divide -- a zero-balance type's accounts all get
            # fixed_share 0.0 (mirrors
            # resolution._traditional_ownership_shares()'s own zero-guard
            # and 011 research.md §2's "can only ever stay zero"
            # reasoning, generalized to every account type here).
            fixed_share = (account.balance / pool) if pool > 0 else 0.0
        # rp-cgj: both are documented (Account's own field docstrings) as
        # never None for an account this function actually sees --
        # account_id is always auto-filled by parse_scenario(), and owner
        # is only ever None transiently, before validation, or for a
        # Scenario built directly rather than parsed; this function's own
        # docstring says it's called once per request against an
        # already-resolved scenario's accounts.
        assert account.account_id is not None
        assert account.owner is not None
        shares.append(
            AccountShare(
                account_id=account.account_id,
                account_type=account.account_type,
                owner=account.owner,
                inherited=account.inherited is not None,
                fixed_share=fixed_share,
            )
        )
    return shares


def _within_member_shares(shares: list[AccountShare], member: str) -> dict[str, float]:
    """That member's own traditional (ordinary) accounts' balances,
    expressed as a share of that SAME member's own subtotal (research.md
    §2) -- distinct from AccountShare.fixed_share, which is relative to
    the whole household's pooled type total. Used only to sub-allocate a
    member's own exact RMD across their own multiple traditional
    accounts, when they have more than one (data-model.md §
    AccountYearDetail's rmd_amount)."""
    member_shares = [s for s in shares if not s.inherited and s.account_type == "traditional" and s.owner == member]
    # fixed_share is proportional to each account's own starting balance
    # (same denominator cancels), so their *relative* weights already
    # encode within-member proportion -- normalize against just this
    # member's own accounts rather than re-deriving from raw balances.
    total = sum(s.fixed_share for s in member_shares)
    if total <= 0:
        return {s.account_id: 0.0 for s in member_shares}
    return {s.account_id: s.fixed_share / total for s in member_shares}


def _withdrawal_totals_by_type(year) -> dict[AccountType, float]:
    """This year's total withdrawal per account type -- the pooled RMD
    amount (traditional only) plus both withdrawal passes' sequence line
    items (spending-need and tax-funding), summed per type."""
    totals: dict[AccountType, float] = {"traditional": year.mechanics.withdrawal_plan.rmd_drawn, "roth": 0.0, "taxable": 0.0}
    for item in (*year.mechanics.withdrawal_plan.sequence_withdrawals, *year.tax_funding_withdrawal.sequence_withdrawals):
        totals[item.account_type] += item.amount
    return totals


def attribute_plan_projection(
    projection: PlanProjection,
    shares: list[AccountShare],
) -> list[PlanYearAccountDetail]:
    """One PlanYearAccountDetail per projection.years entry (data-model.md
    § AccountYearDetail's field-by-field derivation). Pure function --
    projection and shares are read, never mutated."""
    ordinary_shares = [s for s in shares if not s.inherited]
    inherited_shares = {s.account_id: s for s in shares if s.inherited}

    member_traditional_account_counts: dict[str, int] = {}
    for share in ordinary_shares:
        if share.account_type == "traditional":
            member_traditional_account_counts[share.owner] = member_traditional_account_counts.get(share.owner, 0) + 1
    within_member_shares_by_member = {
        member: _within_member_shares(ordinary_shares, member)
        for member, count in member_traditional_account_counts.items()
        if count > 1
    }

    results: list[PlanYearAccountDetail] = []
    for year in projection.years:
        rows: list[AccountYearDetail] = []
        withdrawal_totals = _withdrawal_totals_by_type(year)

        for share in ordinary_shares:
            starting_balance = share.fixed_share * getattr(year.starting_balances, share.account_type)
            ending_balance = share.fixed_share * getattr(year.ending_balances, share.account_type)
            withdrawal_amount = share.fixed_share * withdrawal_totals[share.account_type]

            if share.account_type != "traditional":
                rmd_amount = 0.0
                attribution: Attribution = "fixed_share_of_pooled_total"
            else:
                member_total_rmd = year.member_rmd_amounts.get(share.owner, 0.0)
                if share.owner in within_member_shares_by_member:
                    rmd_amount = member_total_rmd * within_member_shares_by_member[share.owner].get(share.account_id, 0.0)
                    attribution = "fixed_share_of_pooled_total"
                else:
                    rmd_amount = member_total_rmd
                    attribution = "independently_tracked"

            rows.append(
                AccountYearDetail(
                    account_id=share.account_id,
                    account_type=share.account_type,
                    owner=share.owner,
                    starting_balance=starting_balance,
                    ending_balance=ending_balance,
                    rmd_amount=rmd_amount,
                    withdrawal_amount=withdrawal_amount,
                    attribution=attribution,
                )
            )

        # -- inherited accounts: exact by construction, passthrough of
        # PlanYearProjection's own already-independently-tracked snapshot
        # (research.md §3) -- never participates in share math. Metadata
        # (account_type/owner) comes from compute_account_shares()'s own
        # inherited-account entries, since PlanYearProjection's snapshot
        # dicts are keyed by account_id -> dollar amount only.
        for account_id, ending_balance in year.inherited_account_balances.items():
            distribution = year.inherited_account_distributions.get(account_id, 0.0)
            meta = inherited_shares.get(account_id)
            rows.append(
                AccountYearDetail(
                    account_id=account_id,
                    account_type=meta.account_type if meta is not None else "traditional",
                    owner=meta.owner if meta is not None else "",
                    starting_balance=ending_balance + distribution,  # this year's balance before this year's distribution
                    ending_balance=ending_balance,
                    rmd_amount=distribution,
                    withdrawal_amount=distribution,
                    attribution="independently_tracked",
                )
            )

        results.append(
            PlanYearAccountDetail(
                plan_year=year.plan_year,
                tax_year=year.tax_year,
                accounts=rows,
                member_social_security_benefits=dict(year.member_social_security_benefits),
                member_income_stream_amounts=dict(year.member_income_stream_amounts),
            )
        )

    return results
