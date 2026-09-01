# Data Model: Early-Withdrawal Penalty (Pre-59.5)

## New: `EarlyWithdrawalPenaltyResult` (`retirement_planner.tax`)

```python
@dataclass
class EarlyWithdrawalPenaltyResult:
    """One plan year's 10% early-withdrawal penalty (26 U.S.C. §72(t)(1)),
    applied to the combined taxable early-distribution base a caller has
    already computed. 020-early-withdrawal-penalty data-model.md §
    EarlyWithdrawalPenaltyResult."""

    taxable_early_distribution_base: float
    penalty_owed: float
    figures_used: list[FigureUsage] = field(default_factory=list)
```

- `taxable_early_distribution_base`: echoed back from the caller's input, for audit purposes — the
  combined amount subject to the penalty (research.md Decision 3): each under-59 household member's
  own share of that year's voluntary Traditional withdrawal, plus that year's own unseasoned Roth
  conversion withdrawal amount (`019`).
- `penalty_owed`: `taxable_early_distribution_base * 0.10` — always computed (never skipped), `0.0`
  whenever the base is `0.0`.
- `figures_used`: always carries `EARLY_WITHDRAWAL_PENALTY_RATE`'s usage, regardless of whether
  `penalty_owed` is `0.0` (research.md Decision 5, mirroring NIIT's own "always cited" precedent).

## New: `EARLY_WITHDRAWAL_PENALTY_RATE` (`retirement_planner.tax.early_withdrawal_penalty`)

A `SourcedFigure[float]`, mirroring `_NIIT_RATE`'s own shape — `schedule` maps every documented tax
year to `0.10` (26 U.S.C. §72(t)(1); the age-59½ exception itself is §72(t)(2)(A)(i)). Cross-checked
against the primary source at implementation time before `verified=True` is set, per the
constitution's verified-figure gate.

## Modified: `PlanYearProjection` (`retirement_planner.comparison`)

```python
@dataclass
class PlanYearProjection:
    # ... every existing field, unchanged ...
    early_withdrawal_penalty: EarlyWithdrawalPenaltyResult   # NEW, required (no default)
```

- `early_withdrawal_penalty`: this plan year's own `EarlyWithdrawalPenaltyResult`, mirroring how
  `irmaa: IrmaaResult` and `niit: NiitResult` are already required (non-defaulted) fields on this
  same dataclass — `run_plan_projection()` always computes and populates one every plan year, exactly
  like IRMAA/NIIT, so there is no "opt-out" default to define (unlike `018`'s/`019`'s own additive,
  defaulted fields, which existed to keep a hand-built `PlanYearProjection` construction backward
  compatible — IRMAA's/NIIT's own precedent shows this project does add required fields to this
  dataclass when the new computation is unconditional, not opt-in).

## Modified: `PlanOutcome` (`retirement_planner.comparison`)

```python
@dataclass
class PlanOutcome:
    ending_balance: float
    first_shortfall_plan_year: int | None
    cumulative_tax_paid: float
    cumulative_irmaa_paid: float
    cumulative_niit_paid: float
    cumulative_early_withdrawal_penalty_paid: float   # NEW
```

- `cumulative_early_withdrawal_penalty_paid`: `sum(year.early_withdrawal_penalty.penalty_owed for
  year in years)` — mirrors `cumulative_irmaa_paid`/`cumulative_niit_paid`'s own derivation exactly.
  `cumulative_tax_paid`'s own existing meaning (federal + state income tax only) is unchanged
  (research.md Decision 6, matching `010`'s own precedent for the identical question about
  IRMAA/NIIT).

## Modified: `reporting` package summary type

The Monte Carlo/deterministic summary type `reporting/models.py` already exposes
`median_lifetime_irmaa_paid`/`median_lifetime_niit_paid` gains
`median_lifetime_early_withdrawal_penalty_paid: float`, derived in `reporting/aggregation.py` from
`PlanOutcome.cumulative_early_withdrawal_penalty_paid` (median across Monte Carlo paths, or the
single deterministic value) exactly as the two existing fields already are. `reporting/export.py`'s
CSV column list gains the matching column.

## Derived (computed by `run_plan_projection()`, not stored on any dataclass)

- **Traditional-side base** (one plan year): `sum(traditional_ownership_shares[member.person_name] *
  traditional_sequence_draw for member in household.members if ages_this_year[member.person_name]
  <= 59)`, where `traditional_sequence_draw` is the `"traditional"`-type entry's `amount` in
  `mechanics_result.withdrawal_plan.sequence_withdrawals` (`0.0` if none) — the RMD leg
  (`WithdrawalPlan.rmd_drawn`) is never included (research.md Decision 4).
- **Combined taxable early-distribution base** (one plan year):
  Traditional-side base + `ladder_result.unseasoned_amount_flagged` (`019`'s own already-computed
  result for this same plan year) — passed directly into `compute_early_withdrawal_penalty()`.

## Relationships

- This feature reads `019`'s `RothLadderConsumptionResult.unseasoned_amount_flagged` and `011`'s
  `traditional_ownership_shares` as pure inputs — it modifies neither.
- `PlanYearProjection.early_withdrawal_penalty` and `.unseasoned_roth_withdrawal` (`019`) can both be
  nonzero in the same plan year (Acceptance Scenario US2.2) — the former is *derived from* the
  latter (among other things), not independent of it.
- `PlanOutcome.cumulative_early_withdrawal_penalty_paid` is independent of `cumulative_tax_paid`,
  `cumulative_irmaa_paid`, and `cumulative_niit_paid` — no existing field's own meaning changes.
