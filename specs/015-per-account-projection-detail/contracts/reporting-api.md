# Contract: `retirement_planner.reporting.account_attribution` public API

New sibling module inside the already-existing `retirement_planner.reporting`
package (`specs/006-reporting-aggregation/contracts/reporting-api.md`
covers that package's pre-existing surface — this addendum adds one new
module to it, nothing there changes shape).

## Additive change to `retirement_planner.comparison` (data-model.md)

```python
# comparison/models.py -- PlanYearProjection gains four new fields, all
# field(default_factory=dict); every existing construction call site,
# and every field already documented in
# specs/004-strategy-comparison-layer/contracts/comparison-api.md,
# is otherwise unchanged.

@dataclass
class PlanYearProjection:
    # ...existing fields, unchanged...
    member_rmd_amounts: dict[str, float] = field(default_factory=dict)
    member_social_security_benefits: dict[str, float] = field(default_factory=dict)
    inherited_account_balances: dict[str, float] = field(default_factory=dict)
    inherited_account_distributions: dict[str, float] = field(default_factory=dict)
```

## New module: `retirement_planner.reporting.account_attribution`

```python
from typing import Literal
from dataclasses import dataclass

from retirement_planner.scenario import Account
from retirement_planner.comparison import PlanProjection

AccountType = Literal["traditional", "roth", "taxable"]
Attribution = Literal["independently_tracked", "fixed_share_of_pooled_total"]


@dataclass
class AccountShare:
    account_id: str
    account_type: AccountType
    owner: str
    fixed_share: float  # 0.0-1.0; 0.0 when that type's household total is <= 0


@dataclass
class AccountYearDetail:
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
    plan_year: int
    tax_year: int
    accounts: list[AccountYearDetail]
    member_social_security_benefits: dict[str, float]


def compute_account_shares(accounts: list[Account]) -> list[AccountShare]:
    """One AccountShare per non-inherited account in accounts (data-model.md
    § AccountShare). Pure function of accounts' starting balances -- no
    randomness, no I/O. Excludes any Account with account.inherited is not
    None (those are handled exactly, via PlanYearProjection's inherited_*
    dicts, never via share math -- research.md §3). Raises no exception for
    a zero-balance account type; that type's accounts all get fixed_share
    0.0 (research.md §2's zero-guard, mirroring
    services/bff/src/rp_bff/resolution.py's _traditional_ownership_shares())."""


def attribute_plan_projection(
    projection: PlanProjection,
    shares: list[AccountShare],
) -> list[PlanYearAccountDetail]:
    """One PlanYearAccountDetail per projection.years entry (data-model.md
    § AccountYearDetail's field-by-field derivation). Pure function --
    projection and shares are read, never mutated. shares must be the
    output of compute_account_shares() called against the same scenario
    that produced projection (mismatched account_ids are simply absent
    from the output, never raise)."""
```

## Export (`reporting/__init__.py`)

```python
from .account_attribution import (
    AccountShare,
    AccountYearDetail,
    PlanYearAccountDetail,
    attribute_plan_projection,
    compute_account_shares,
)

__all__ = [
    # ...existing exports, unchanged...
    "AccountShare",
    "AccountYearDetail",
    "PlanYearAccountDetail",
    "attribute_plan_projection",
    "compute_account_shares",
]
```
