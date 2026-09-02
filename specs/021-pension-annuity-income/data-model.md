# Data Model: Pension, Annuity & Phased-Retirement Income Streams

## IncomeStream (new — `scenario.models`)

One generic fixed income source belonging to one `HouseholdMember`.

| Field | Type | Notes |
|---|---|---|
| `label` | `str` | Free-text, user-facing (e.g. "State Teachers' Pension"). Not consumed by any computation — display/audit only. |
| `stream_type` | `Literal["pension", "annuity", "earned_income"]` | Informational classification; does not itself change tax treatment (FR-006/FR-007 — all three are fully taxable ordinary income). Kept as its own field (rather than folded away) so reporting/BRD/UI can group and label streams meaningfully, and so a future feature (e.g. FICA on `earned_income`) has a stable discriminator to key off without a shape change. |
| `start_age` | `int` | The member's age (in whole years, this engine's existing age granularity — see `member_age_in_tax_year()`) at which the stream begins paying. Inclusive. |
| `end_age` | `int \| None` | The member's age through which the stream still pays (inclusive). `None` = pays for every remaining plan year (a lifetime stream) — mirrors `ss_annual_benefit`'s own "once claimed, never stops" behavior. Default `None`. |
| `annual_amount` | `float` | Today's (scenario-start) real dollars, same convention as `annual_need_real`/`ss_annual_benefit`. Must be `>= 0` (validation.py). |
| `inflation_adjustment` | `Literal["cola_adjusted", "fixed_nominal"]` | `cola_adjusted`: pays exactly `annual_amount` every active year (research.md §1). `fixed_nominal`: real amount erodes against `mechanics.income_streams.INFLATION_RATE` (research.md §1). No default — every stream must state its mode explicitly, mirroring `ss_claim_age`'s own no-default precedent for a similarly load-bearing field. |

**Validation** (`validation.py`, `_validate_household()`, extended):
- `end_age is not None and end_age < start_age` → blocking (`"household.members[i].income_streams[j].end_age"`).
- `annual_amount < 0` → blocking (`"household.members[i].income_streams[j].annual_amount"`).

No plausibility (warning-tier) rule is added — `start_age`/`end_age` outside typical retirement ranges (e.g. a stream starting at 25) is not implausible for `earned_income` or an inheritance-funded annuity, unlike `ss_claim_age`'s genuinely bounded [62, 70] range.

## HouseholdMember (extended — `scenario.models`)

Adds one field, additive-only:

```python
income_streams: list[IncomeStream] = field(default_factory=list)
```

Default `[]` reproduces every existing scenario's exact current behavior (FR-001, FR-010) — nothing consumes this field unless it's non-empty.

## PlanYearProjection (extended — `comparison.models`)

Adds one field, mirroring `member_social_security_benefits` exactly:

```python
member_income_stream_amounts: dict[str, float] = field(default_factory=dict)
```

`person_name -> that member's own summed gross income-stream amount this year` (across every stream that member has configured, whether or not each is individually active this year — inactive streams contribute `0.0` to the sum, never omitted). Always populated by `run_plan_projection()`; `{}` only if some other caller constructs a `PlanYearProjection` directly.

## PlanYearAccountDetail (extended — `reporting.account_attribution`)

Same field, same shape, populated the same way `member_social_security_benefits` already is (`dict(year.member_income_stream_amounts)`):

```python
member_income_stream_amounts: dict[str, float] = field(default_factory=dict)
```

## PlanYearMechanicsResult / `compute_plan_year_mechanics()` (extended — `mechanics`)

No new fields on the result type — `income_stream_total` is folded into the existing `ordinary_income` output (research.md §3), the same way `hsa_contribution` already reduces it in place rather than appearing as a separate result field. Two new optional parameters on `compute_plan_year_mechanics()`:

| Parameter | Type | Default | Behavior |
|---|---|---|---|
| `income_stream_total` | `float` | `0.0` | Added into `ordinary_income_established` alongside `rmd_drawn`/`traditional_draws`/`inherited_distribution_drawn`, before `compute_roth_conversion()` runs. `0.0` reproduces every existing call site's exact prior output. |
| `income_stream_figures_used` | `list[FigureUsage] \| None` | `None` | Unioned into the returned `figures_used`, same pattern as `rmd_figures_used`/`inherited_rmd_figures_used`. |

## `IncomeStreamAmountResult` (new — `mechanics.models`)

```python
@dataclass
class IncomeStreamAmountResult:
    amount: float
    figures_used: list[FigureUsage]
```

Returned by the new `compute_income_stream_amount()` (mechanics.income_streams), which takes an `IncomeStream`'s fields as plain values (`annual_amount`, `inflation_adjustment`, `start_age`, `end_age`) rather than an `IncomeStream` instance — mechanics is a pure calculator over explicit inputs, never scenario dataclasses (mirrors `compute_social_security_benefit()`'s own PIA/FRA/claiming_age signature). `amount` is `0.0` and `figures_used` is `[]` for a plan year the stream isn't active in, or for a `cola_adjusted` stream in any year (no figure needed — a flat pass-through has nothing to cite). `figures_used` carries exactly `[INFLATION_RATE.usage_for_year(tax_year)]` for an active `fixed_nominal` stream.

## Relationships

- `Household.members[*].income_streams[*]` — zero or more per member, independent of every other member's own streams (Edge Cases: overlap is summed, not merged or deduplicated).
- `mechanics.income_streams.compute_income_stream_amount()` is a pure function of `(IncomeStream, member_age_this_year: int, tax_year: int, reference_tax_year: int)` — no dependency on account balances, filing status, or any other stream (parallels `compute_social_security_benefit()`'s own independence).
- `comparison.projection._member_income_stream_amounts()` sums every member's own streams' amounts for one tax year into a `dict[person_name, float]` (mirrors `_member_gross_social_security_benefits()`), whose values sum to the `income_stream_total` passed into `compute_plan_year_mechanics()`.

## Consumption expectations for downstream features

- `services/bff`'s `HouseholdMemberRequest` gains a mirrored `income_streams: list[IncomeStreamRequest] = []` (schemas.py) — no `resolution.py` change needed (research.md §6).
- `apps/streamlit_ui`'s `1_Scenarios.py` preserves (does not silently drop) a loaded scenario's `income_streams` on save, without exposing editing widgets this iteration (plan.md Scope Boundaries).
- A downstream FICA/payroll-tax feature (explicitly out of scope, spec.md Assumptions) would key off `stream_type == "earned_income"` — the field is already shaped for that extension without a further shape change.
