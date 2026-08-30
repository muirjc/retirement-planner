# Data Model: Social Security Claiming-Age Actuarial Adjustment

## Modified: `HouseholdMember` (`retirement_planner.scenario`, `001`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float          # MEANING CHANGE: now the member's PIA
                                       # (benefit payable if claimed exactly
                                       # at full_retirement_age), not the
                                       # amount paid at ss_claim_age.
    full_retirement_age: float | None = None   # NEW
    hdhp_coverage: bool = False
```

- `full_retirement_age`: the member's Social Security full retirement age, in years (fractional
  allowed, e.g. `66.8333` for 66 years 10 months). `None` (the YAML-omitted case) means "assume this
  member's FRA equals their `ss_claim_age`" — i.e., no adjustment — research.md Decision 3.
  `parse_scenario()` performs this defaulting so every other consumer of `HouseholdMember`
  (`validation.py`, `comparison/projection.py`) always sees a concrete `float`, never `None`, exactly
  as `Account.owner`'s single-member auto-fill already works (`loader.py`'s existing precedent).
- `ss_annual_benefit`: shape unchanged (`float`); only its documented meaning changes, in this
  dataclass's own docstring and in `docs/BRD.md`.

## New: `SocialSecurityBenefitResult` (`retirement_planner.mechanics`)

```python
@dataclass
class SocialSecurityBenefitResult:
    """One member's actual annual Social Security benefit, adjusted for how
    their claiming_age compares to their full_retirement_age."""

    annual_benefit: float
    """The PIA, reduced for early claiming or increased for delayed claiming
    -- equals primary_insurance_amount exactly when claiming_age ==
    full_retirement_age."""
    adjustment_factor: float
    """annual_benefit / primary_insurance_amount, e.g. ~0.70 at 62 against a
    67 FRA, 1.0 at FRA, ~1.24 at 70 against a 67 FRA -- surfaced separately
    from annual_benefit so a caller/report can show "70% of PIA" without
    re-deriving it from two floats."""
    figures_used: list[FigureUsage]
```

Mirrors `RmdResult`'s existing shape (`required_amount` + a derived descriptor + `figures_used`) — see
`mechanics/models.py`.

## New (private): `_ClaimingAgeAdjustmentRates` + `SS_CLAIMING_AGE_ADJUSTMENT` (`mechanics/social_security_benefit.py`)

```python
@dataclass
class _ClaimingAgeAdjustmentRates:
    early_reduction_rate_tier_1: float   # 5/9 of 1% = 0.0555...% per month, first 36 months early
    early_reduction_rate_tier_2: float   # 5/12 of 1% per month, additional months beyond 36
    early_reduction_tier_1_months: int   # 36
    delayed_credit_rate_per_month: float # 2/3 of 1% = 0.0833...% per month
    max_claiming_age_for_credit: int     # 70 -- no further credit accrues past this age

SS_CLAIMING_AGE_ADJUSTMENT: SourcedFigure[_ClaimingAgeAdjustmentRates] = SourcedFigure(
    name="ss_claiming_age_adjustment_rates",
    schedule={year: _RATES for year in _DOCUMENTED_YEARS},   # one flat rate set, like tax/social_security.py's thresholds
    citation="42 U.S.C. §402(q) (early retirement reduction), §402(w) (delayed retirement credit); "
              "20 C.F.R. §404.410, §404.313 (implementing rates)",
    last_verified=date(...),   # set at implementation time, after cross-checking the regulation text
    verified=True,             # only once actually cross-checked -- see constitution's verified-figure gate
)
```

Not part of the public `mechanics` contract (private, `_`-prefixed) — only
`compute_social_security_benefit()` and `SocialSecurityBenefitResult` are exported, mirroring how
`mechanics/rmd.py` exports `UNIFORM_LIFETIME_TABLE` itself (public, since RMD callers may want to
inspect the table) but this feature's rate table has no such external consumer identified in spec.md,
so it stays private unless a later feature needs it (`RMD_START_AGE` and `UNIFORM_LIFETIME_TABLE` are
public because `mechanics/__init__.py` already re-exports them for exactly that reason — this feature
does not need the same treatment unless a caller shows up wanting it).

## New operation: `compute_social_security_benefit()` (`retirement_planner.mechanics`)

```python
def compute_social_security_benefit(
    primary_insurance_amount: float,
    full_retirement_age: float,
    claiming_age: int,
    tax_year: int,
) -> SocialSecurityBenefitResult:
    """Derives the annual benefit actually paid at claiming_age, given the
    member's PIA and FRA (FR-002-FR-005). claiming_age exactly equal to
    full_retirement_age (accounting for full_retirement_age's own fractional
    part) returns annual_benefit == primary_insurance_amount unchanged.
    claiming_age < full_retirement_age applies the tiered early-reduction
    formula; claiming_age > full_retirement_age applies the delayed credit,
    capped at max_claiming_age_for_credit. Raises UnsupportedTaxYearError if
    the adjustment-rate figure has no schedule entry for tax_year (mirrors
    every other SourcedFigure-backed operation in this codebase)."""
```

Validation of `claiming_age`'s 62-70 range is `validation.py`'s job (already enforced, research.md
Decision 5) — this function itself does not re-validate range, consistent with `compute_rmd()` and
`compute_taxable_social_security()` both trusting their callers to have already run `validate()`.

## Modified: `_member_gross_social_security_benefits()` (`comparison/projection.py`)

Signature changes from `dict[str, float]` to `tuple[dict[str, float], list[FigureUsage]]`: for each
member who has reached their claiming age this plan year, calls `compute_social_security_benefit()`
(using the member's `ss_annual_benefit` as PIA, `full_retirement_age`, and this comparison's
`claiming_ages[member.person_name]`) instead of returning `member.ss_annual_benefit` directly; collects
every result's `figures_used` into the second return value. `run_plan_projection()`'s existing
`figures_used = [*mechanics_result.figures_used, *federal_tax.figures_used, ...]` list gains this new
source, so the SS claiming-age adjustment figure appears in every plan year's audit trail exactly like
every other figure already does.

**Implementation-time addition**: `full_retirement_age`'s None-to-`ss_claim_age` default is resolved
a second time here, not only relied on from `parse_scenario()`'s own resolution — mirroring
`validation.py`'s existing "not just relied on from `parse_scenario()`'s own auto-fill" precedent for
`Account.owner`. This was discovered necessary during implementation: a `Household` built directly
(bypassing the loader), as most of this codebase's own test fixtures do, would otherwise reach
`compute_social_security_benefit()` with `full_retirement_age=None` and raise `TypeError`.

## Modified: `docs/BRD.md`

- §6.2 (Social Security taxability) gains a new subsection (or a new §6.2a) describing the
  claiming-age benefit adjustment: the PIA/FRA model, the early-reduction and delayed-credit formulas,
  and their citation.
- §2.1 (In scope)'s existing "Social Security claiming-age sensitivity (a full 62-70 grid per spouse)"
  bullet gets a short parenthetical noting the grid now varies benefit *amount*, not just timing.
- Any prose implying claiming age only changes *when* income starts (if present) is corrected.

## Validation rule addition: `validation.py::_validate_household()`

New warning-severity check: a member whose `full_retirement_age` (after `parse_scenario()`'s default
resolution) falls outside `[65.0, 67.0]` gets:

```python
ValidationFlag(
    field=f"household.members[{index}].full_retirement_age",
    message=(
        f"Full retirement age {member.full_retirement_age} is outside the "
        "plausible range (65-67) Social Security's own rules can produce; "
        "double-check this value."
    ),
    severity="warning",
)
```

No change to the existing `ss_claim_age` 62-70 blocking check (already present, already correct per
research.md Decision 5).
