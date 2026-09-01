# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`, `016`, `017`)

Extends `specs/017-ss-spousal-survivor-benefits/contracts/scenario-api.md` (itself extending
`016`/`010`/`001`) with one additive field on `Household`. `parse_scenario()`, `validate()`,
`save_scenario()`, `list_scenarios()`, `load_scenario()`, `delete_scenario()`, and every existing
field are unchanged in shape.

## Modified data types (`models`)

```python
@dataclass
class Household:
    filing_status: Literal["single", "married_filing_jointly"]
    members: list[HouseholdMember]
    survivor_spending_reduction_pct: float = 0.0   # NEW
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Consumption expectations for downstream features

- `survivor_spending_reduction_pct` defaults to `0.0` and is round-tripped by `parse_scenario()`/
  `save_scenario()` like any other optional field. `0.0` is already this field's fully-meaningful
  "no reduction" no-op value — no defaulting/resolution logic beyond the plain YAML-omitted-key
  default is needed (mirrors `hdhp_coverage`'s pattern, not `full_retirement_age`'s computed-default
  one).
- `retirement_planner.comparison.run_plan_projection()` (see `contracts/comparison-api.md` addendum)
  is the only consumer of this field — `retirement_planner.scenario` itself only stores and
  round-trips it.
- `services/bff`'s `HouseholdRequest` (`007`) gains the same field, mirroring this shape exactly
  (`survivor_spending_reduction_pct: float = 0.0`) — see plan.md's Project Structure.
- `validation.py` gains one new rule (not part of this contract's shape, but noted here since it
  reads this field): a **warning** when the value falls outside `[0.0, 1.0]` (data-model.md).
