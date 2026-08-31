# Data Model: Social Security Spousal and Survivor Benefits

## Modified: `HouseholdMember` (`retirement_planner.scenario`, `001`, extended by `016`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float          # PIA (016) -- unchanged by this feature
    full_retirement_age: float | None = None    # 016 -- unchanged by this feature
    hdhp_coverage: bool = False
    predicted_death_age: int | None = None   # NEW
```

- `predicted_death_age`: this member's hypothetical age at death, for planning purposes — a "what
  if" input, not a record of an already-happened event (contrast `012`'s
  `InheritedIraDetails.death_year`, research.md Decision 6). `None` (the default, and every scenario
  predating this feature) means "no hypothetical death is configured" — this feature and every
  existing computation ignore this member entirely with respect to mortality; `rp-g8y` is the future
  feature that will actually consult it to change a running projection's behavior once a plan year
  reaches this age.
- Consulted by nothing in this feature's own computations (`compute_spousal_benefit_floor()` and
  `compute_survivor_benefit()` are both pure functions over benefit amounts, not over
  `HouseholdMember` itself) — it exists purely as the data-model home `rp-g8y` needs, added now so
  that feature is additive against an already-stable shape rather than needing its own
  `scenario`-package change.

## New: `SpousalBenefitResult` (`retirement_planner.mechanics`)

```python
@dataclass
class SpousalBenefitResult:
    """One member's spousal-derived Social Security amount -- up to 50%
    of their spouse's PIA, adjusted for the claiming member's own
    claiming age relative to their own FRA."""

    spousal_amount: float
    """0.5 * other_member_pia, reduced for the claiming member's own
    early claiming (spousal-specific rate); never increased for delayed
    claiming -- capped at exactly 0.5 * other_member_pia for claiming at
    or after the claiming member's own FRA (no delayed-retirement credit
    on a spousal amount, research.md Decision 2)."""
    adjustment_factor: float
    """spousal_amount / (0.5 * other_member_pia), e.g. ~0.65 at 62
    against a 67 FRA (25% + 10% reduction), 1.0 at or after FRA -- never
    > 1.0, unlike SocialSecurityBenefitResult.adjustment_factor which can
    exceed 1.0 for delayed claiming."""
    figures_used: list[FigureUsage]
```

Mirrors `SocialSecurityBenefitResult`'s existing shape (an amount + a derived descriptor +
`figures_used`) — see `mechanics/models.py`.

## New: `SurvivorBenefitResult` (`retirement_planner.mechanics`)

```python
@dataclass
class SurvivorBenefitResult:
    """The surviving member's ongoing Social Security benefit after one
    member has died -- the higher of the two members' own currently-
    claimed benefit amounts (research.md Decision 4)."""

    survivor_benefit: float
    """max(member_a_benefit, member_b_benefit)."""
    figures_used: list[FigureUsage]
```

## New (private): `_SpousalAdjustmentRates` + `SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT` (`mechanics/social_security_benefit.py`)

```python
@dataclass
class _SpousalAdjustmentRates:
    early_reduction_rate_tier_1: float   # 25/36 of 1% per month, first 36 months early
    early_reduction_rate_tier_2: float   # 5/12 of 1% per month, additional months beyond 36
    early_reduction_tier_1_months: int   # 36

SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT: SourcedFigure[_SpousalAdjustmentRates] = SourcedFigure(
    name="ss_spousal_claiming_age_adjustment_rates",
    schedule={year: _SPOUSAL_RATES for year in _DOCUMENTED_YEARS},
    citation="42 U.S.C. §402(b)/(c) (wife's/husband's insurance benefits); "
             "20 C.F.R. §404.410 (wife's/husband's benefit reduction: 25/36 of 1% per month "
             "for the first 36 months claimed early, 5/12 of 1% per month beyond that; no "
             "delayed-retirement credit applies to a spousal amount)",
    last_verified=date(...),   # set at implementation time, after cross-checking the regulation text
    verified=True,             # only once actually cross-checked -- constitution's verified-figure gate
)
```

Private (`_`-prefixed), like 016's own `_ClaimingAgeAdjustmentRates`/`SS_CLAIMING_AGE_ADJUSTMENT` —
no external consumer identified in spec.md beyond `compute_spousal_benefit_floor()` itself.

## New (private): `SS_SURVIVOR_BENEFIT_RULE` (`mechanics/social_security_benefit.py`)

```python
SS_SURVIVOR_BENEFIT_RULE: SourcedFigure[None] = SourcedFigure(
    name="ss_survivor_benefit_rule",
    schedule={year: None for year in _DOCUMENTED_YEARS},
    citation="42 U.S.C. §402(e)/(f) (widow's/widower's insurance benefits); 20 C.F.R. §404.335/"
             "§404.336 -- the surviving spouse's benefit is the higher of the two spouses' own "
             "benefit amounts; this feature does not model the widow(er)'s-own early-claiming "
             "reduction or the statutory 'widow's limit' cap (spec.md Assumptions, a documented "
             "simplification)",
    last_verified=date(...),
    verified=True,
)
```

`SourcedFigure[None]` — an intentional, if unusual, instantiation of the existing generic: the
"higher of the two continues" rule has no year-varying numeric parameter to schedule, but this
project's `FigureUsage`/audit-trail convention (`tax/models.py`'s `SourcedFigure` docstring: "The
auditability primitive... one `SourcedFigure` corresponds to one real-world citation") applies just
as much to a categorical rule as to a table — wrapping it this way is what lets
`compute_survivor_benefit()` produce a `FigureUsage` the same way every other cited computation in
this codebase already does (research.md Decision 4's rationale references this same design choice).

## New operations (`mechanics/social_security_benefit.py`)

```python
def compute_spousal_benefit_floor(
    other_member_pia: float,
    full_retirement_age: float,
    claiming_age: int,
    tax_year: int,
) -> SpousalBenefitResult:
    """Derives the spousal-derived amount available to a member claiming
    at claiming_age (relative to their OWN full_retirement_age), based
    on the OTHER member's raw PIA (FR-001, FR-003). Returns
    spousal_amount == 0.5 * other_member_pia, adjustment_factor == 1.0
    when claiming_age >= full_retirement_age (no delayed credit, ever).
    Applies the tiered spousal early-reduction formula (25/36 of 1% per
    month for the first 36 months claimed early, 5/12 of 1% per month
    beyond that) when claiming_age < full_retirement_age. Raises
    UnsupportedTaxYearError if the adjustment-rate figure has no
    schedule entry for tax_year."""


def compute_survivor_benefit(
    member_a_benefit: float,
    member_b_benefit: float,
    tax_year: int,
) -> SurvivorBenefitResult:
    """Returns the higher of the two currently-claimed benefit amounts
    as the survivor's ongoing benefit (FR-005) -- the caller is
    responsible for attributing this amount to whichever member is
    actually still living; this function's result does not depend on
    which one that is (research.md Decision 4). Raises
    UnsupportedTaxYearError if SS_SURVIVOR_BENEFIT_RULE has no schedule
    entry for tax_year (in practice never, given _DOCUMENTED_YEARS'
    range -- consulted purely for the citation trail, mirroring every
    other SourcedFigure-backed operation in this codebase)."""
```

`retirement_planner.mechanics.__init__` re-exports both functions and both new result types
alongside the module's existing exports.

## Modified: `_member_gross_social_security_benefits()` (`comparison/projection.py`)

After computing each member's own claiming-age-adjusted benefit exactly as 016 already does, for a
`"married_filing_jointly"` household with exactly two members: once **both** members have reached
their own claiming age this plan year (research.md Decision 3), compute each member's
`compute_spousal_benefit_floor()` using the *other* member's raw `ss_annual_benefit` (PIA) as
`other_member_pia` and this member's own `full_retirement_age`/`claiming_ages[...]` — then replace
that member's benefit with `max(own_benefit, spousal_amount)`. A `"single"`-filing-status household
(FR-004), or an MFJ household where one member hasn't yet claimed, skips this step entirely for that
member — reproducing today's output exactly. `figures_used` gains
`SS_SPOUSAL_CLAIMING_AGE_ADJUSTMENT`'s usage only for a member whose spousal amount was actually
computed (never for a `"single"` household, or before both members have claimed) — mirrors this
codebase's existing "a figure consulted but not ultimately used does not appear in `figures_used`"
convention (`002`'s own data-model.md § Relationships).

`compute_survivor_benefit()` is **not** called from this function, or anywhere else in the engine, by
this feature (FR-007) — it is implemented, tested, and cited, and exists for `rp-g8y` to call once
that feature wires mortality into the per-year loop.

## New validation rules: `validation.py::_validate_household()`

```python
# Blocking: a "prediction" of a death age already in the past is incoherent, not merely implausible.
if member.predicted_death_age is not None and member.predicted_death_age < member.current_age:
    ValidationFlag(
        field=f"household.members[{index}].predicted_death_age",
        message=(
            f"Predicted death age {member.predicted_death_age} is less than this member's "
            f"current age ({member.current_age}); a predicted death age cannot be in the past."
        ),
        severity="blocking",
    )

# Warning: outside [50, 110] (simulation/survival_data.py's own SURVIVAL_TABLE age range),
# mirroring 016's own full_retirement_age plausibility-warning pattern exactly.
if member.predicted_death_age is not None and not (50 <= member.predicted_death_age <= 110):
    ValidationFlag(
        field=f"household.members[{index}].predicted_death_age",
        message=(
            f"Predicted death age {member.predicted_death_age} is outside the plausible "
            "range (50-110); double-check this value."
        ),
        severity="warning",
    )
```

Both checks are skipped entirely when `predicted_death_age is None` (every existing scenario) —
strictly additive.

## Modified: `docs/BRD.md`

- §5.3 ("Federal — not modeled")'s existing spousal/survivor bullet is rewritten: the spousal floor
  is now modeled (and wired into every projection); the survivor-benefit *calculation* is available
  and cited but not yet wired into a running projection (tracked as `rp-g8y`); the family maximum
  benefit and deemed-filing mechanics are named as the specific remaining gaps (research.md
  Decision 8).
- §6.2a's closing "Explicitly not modeled" paragraph drops spousal/survivor benefits from that list
  (only the earnings test remains there) and gains a new subsection describing the spousal-floor and
  survivor-benefit formulas, mirroring the claiming-age-adjustment subsection immediately above it.
