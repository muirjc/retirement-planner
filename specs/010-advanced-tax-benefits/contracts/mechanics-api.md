# Contract: `retirement_planner.mechanics` public API (addendum to `003`)

Extends `specs/003-retirement-account-mechanics/contracts/mechanics-api.md` with the new `hsa` module. Everything else in that contract is unchanged — `compute_rmd()`, `compute_roth_conversion()`, `compute_withdrawal_plan()`, and `compute_plan_year_mechanics()`'s existing parameters keep their exact locked shape (see below for the one additive parameter `compute_plan_year_mechanics()` gains).

**Correction during implementation (T022)**: the original draft of `HsaEligibility` omitted `age`. `compute_hsa_contribution()` needs each eligible member's age to determine 55+ catch-up eligibility, and the only place that fits without adding a second, easy-to-desync parameter is on `HsaEligibility` itself — `compute_hsa_eligibility()` already receives age per member and simply carries it through.

## New data types (`models`)

```python
@dataclass
class HsaEligibility:
    person_name: str
    age: int
    eligible: bool
    reason: str | None

@dataclass
class HsaContributionResult:
    eligible_members: list[HsaEligibility]
    applicable_limit: float
    amount_contributed: float
    rejected_reason: str | None
    figures_used: list[FigureUsage]
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## New operations (`hsa`)

```python
# retirement_planner.mechanics.hsa:

def compute_hsa_eligibility(
    members: list[tuple[str, int, bool]],  # (person_name, age_this_year, hdhp_coverage)
    medicare_enrolled: dict[str, bool],     # person_name -> enrolled this plan year
) -> list[HsaEligibility]:
    """Determines each household member's HSA eligibility for one plan
    year: eligible iff hdhp_coverage is True and medicare_enrolled is
    False for that member (FR-008-FR-010) -- one member's result never
    depends on another member's coverage or enrollment status."""


def compute_hsa_contribution(
    eligibility: list[HsaEligibility],
    configured_annual_amount: float,
    tax_year: int,
) -> HsaContributionResult:
    """Looks up tax_year's HSA contribution limits (self-only if exactly
    one eligible member, family if two or more, plus a per-eligible-
    member 55+ catch-up), and sets amount_contributed to
    min(configured_annual_amount, applicable_limit), or 0.0 with a
    rejected_reason when no member is eligible this plan year (FR-012,
    research.md §5 -- never raises for the ordinary "not eligible this
    year" case, only for an undocumented tax_year's limit figure).
    Raises UnsupportedTaxYearError if the limit figure has no entry for
    tax_year."""
```

## Modified operation

```python
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
    hsa_contribution: HsaContributionResult | None = None,  # NEW, optional,
        # defaults to None (no HSA modeled -- reproduces this function's
        # exact current behavior when omitted)
) -> PlanYearMechanicsResult:
    """Unchanged existing behavior, plus: when hsa_contribution is
    provided, its amount_contributed reduces the returned
    PlanYearMechanicsResult.ordinary_income by that same amount (FR-011),
    and its figures_used are folded into the returned result's
    figures_used union, alongside rmd_figures_used and the conversion's
    own figures_used."""
```

## Consumption expectations for downstream features

- `004-strategy-comparison-layer`'s `run_plan_projection()` computes `HsaContributionResult` once per plan year (via `compute_hsa_eligibility()` then `compute_hsa_contribution()`, using that year's own `ages_this_year` the loop already computes) and passes it into `compute_plan_year_mechanics()` — no other feature is expected to call `hsa.py` directly.
- `compute_plan_year_mechanics()`'s new parameter is optional and defaults to reproducing today's exact behavior — every existing caller (including every existing test) continues to work unmodified until it opts in.
