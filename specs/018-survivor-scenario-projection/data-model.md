# Data Model: Survivor Scenario Projection Wiring

## Modified: `Household` (`retirement_planner.scenario`, `001`)

```python
@dataclass
class Household:
    filing_status: Literal["single", "married_filing_jointly"]
    members: list[HouseholdMember]
    survivor_spending_reduction_pct: float = 0.0   # NEW
```

- `survivor_spending_reduction_pct`: the fraction (0.0-1.0) by which `annual_spending_need` is reduced
  for every plan year *after* a configured member death takes effect (spec.md FR-004). `0.0` (the
  default, and every scenario predating this feature) is a true no-op — spending stays at its full,
  configured value even after a death, reproducing every existing scenario's exact current behavior.
  Consulted only when `run_plan_projection()` determines a plan year is post-death (see Derived,
  below) — a household with no member's `predicted_death_age` configured never reads this field at
  all, regardless of its value, matching `017`'s own "an unconsulted opt-in field" precedent for
  `predicted_death_age` itself.
- Plausibility: a value outside `[0.0, 1.0]` is flagged as a `warning` (not blocking — an intentional
  household choice to model spending going *up* after a death, e.g. new caregiving costs, is a
  legitimate if unusual planning scenario, so this is a double-check prompt, not a hard rejection),
  mirroring `full_retirement_age`'s and `predicted_death_age`'s own existing plausibility-warning
  pattern (`016` FR-009, `017` Edge Cases).

## Unchanged: `HouseholdMember.predicted_death_age` (`017`)

This feature is the first and only consumer of `predicted_death_age` (`017` added the field
specifically for this feature — see that feature's own data-model.md). No shape change here; only new
*behavior* that reads it (see Derived, below).

## Modified: `PlanYearProjection` (`retirement_planner.comparison`)

```python
@dataclass
class PlanYearProjection:
    plan_year: int
    tax_year: int
    mechanics: PlanYearMechanicsResult
    federal_tax: FederalTaxResult
    state_tax: StateTaxResult
    tax_funding_withdrawal: WithdrawalPlan
    starting_balances: AccountBalances
    ending_balances: AccountBalances
    shortfall: float
    irmaa: IrmaaResult
    niit: NiitResult
    hsa_contribution: HsaContributionResult
    figures_used: list[FigureUsage] = field(default_factory=list)
    member_rmd_amounts: dict[str, float] = field(default_factory=dict)
    member_social_security_benefits: dict[str, float] = field(default_factory=dict)
    inherited_account_balances: dict[str, float] = field(default_factory=dict)
    inherited_account_distributions: dict[str, float] = field(default_factory=dict)
    filing_status: Literal["single", "married_filing_jointly"] | None = None   # NEW
    effective_spending_need: float = 0.0   # NEW
```

- `filing_status`: the *effective* filing status this specific plan year's `federal_tax`/`state_tax`/
  `irmaa`/`niit` results were actually computed with — `household.filing_status` unchanged through the
  death year (inclusive) and every year before it; forced to `"single"` for every plan year after a
  configured death takes effect (spec.md FR-002). Always populated by `run_plan_projection()`; `None`
  only if some other caller constructs a `PlanYearProjection` directly without setting it (mirrors
  every other `015`-introduced additive field's own default-value precedent). For a household with no
  configured death, every year's value equals `household.filing_status` — a strict, informative
  addition, not a change to any existing computed number.
- `effective_spending_need`: the actual `spending_need` value passed into `compute_plan_year_mechanics()`
  this plan year — `annual_spending_need` unchanged through the death year (inclusive) and every year
  before it; `annual_spending_need * (1 - household.survivor_spending_reduction_pct)` for every plan
  year after (spec.md FR-004). No existing type in the `mechanics` package echoes back its own
  `spending_need` input (confirmed by reading `mechanics/models.py`), so this is recorded here, on
  `PlanYearProjection` (a `comparison`-package type this feature already modifies), rather than adding
  a new field to a `mechanics` result type never before extended for this purpose. Always populated by
  `run_plan_projection()`; `0.0` only if some other caller constructs a `PlanYearProjection` directly
  without setting it. For a household with no configured death or no configured reduction percentage,
  every year's value equals `annual_spending_need` unchanged.
- `member_social_security_benefits` (`015`, unchanged in shape): for a post-death plan year, the
  deceased member's entry becomes `0.0` and the surviving member's entry becomes
  `compute_survivor_benefit()`'s result (research.md Decision 3) — the dict's keys are unchanged
  (still every `household.members[*].person_name`), only the post-death values differ from what a
  same-inputs pre-`018` projection would have produced.

## Derived (computed by `run_plan_projection()`, not stored on any dataclass)

- **Household death tax year**: for an MFJ household (`filing_status == "married_filing_jointly"` and
  `len(members) == 2`) where at least one member has `predicted_death_age` set, the first tax year
  that member's translated age (`member_age_in_tax_year()`) reaches `predicted_death_age`. When both
  members have it configured, the *earlier* of the two tax years is used (spec.md Edge Cases) — the
  survivor's own later configured death has no further modeled effect. `None` for a `"single"`
  household or an MFJ household where neither member has it configured (research.md Decision 1).
- **Post-death plan year**: any plan year whose `tax_year` is strictly greater than the household
  death tax year above. The death year itself, and every year before it, is a pre-death plan year
  (spec.md Edge Cases — mirrors real income-tax law's allowance of a joint return for the year a
  spouse actually dies, without this engine modeling Qualifying Surviving Spouse status for the years
  after).

## Relationships

- `Household.survivor_spending_reduction_pct` and `HouseholdMember.predicted_death_age` are
  independent fields — a household can configure a spending reduction with no death configured (inert,
  since there is no post-death year to apply it to) or a death with no spending reduction configured
  (defaults to `0.0`, full spending continues). Only their *combination*, consumed together by
  `run_plan_projection()`, produces the survivor-scenario spending effect.
- `PlanYearProjection.filing_status`, `.effective_spending_need`, and `.member_social_security_benefits`
  all change together, driven by the same single "is this plan year post-death?" determination — there
  is no state where one reflects the switch and another doesn't.
