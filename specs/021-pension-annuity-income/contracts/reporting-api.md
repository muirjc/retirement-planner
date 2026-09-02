# Contract: `retirement_planner.reporting` public API (addendum to `015`)

`compute_account_shares()` and `attribute_plan_projection()` keep their existing locked signatures.

## Modified data type (`account_attribution`)

```python
@dataclass
class PlanYearAccountDetail:
    plan_year: int
    tax_year: int
    accounts: list[AccountYearDetail] = field(default_factory=list)
    member_social_security_benefits: dict[str, float] = field(default_factory=dict)
    member_income_stream_amounts: dict[str, float] = field(default_factory=dict)   # NEW
```

## Modified operation (`attribute_plan_projection`)

For each `PlanYearAccountDetail` constructed, `member_income_stream_amounts=dict(year.member_income_stream_amounts)` is set alongside the existing `member_social_security_benefits=dict(year.member_social_security_benefits)` — copied from the corresponding `comparison.PlanYearProjection` (`comparison-api.md` addendum), same shallow-copy discipline, no other field's construction changes.
