# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`)

Extends `specs/001-scenario-config-management/contracts/scenario-api.md` (as already extended by
`specs/010-advanced-tax-benefits/contracts/scenario-api.md`) with one additive field and one
meaning-only change. `parse_scenario()`, `validate()`, `save_scenario()`, `list_scenarios()`,
`load_scenario()`, `delete_scenario()`, and every other existing field are unchanged in shape.

## Modified data types (`models`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float          # MEANING CHANGE, same shape: now the
                                       # member's Primary Insurance Amount
                                       # (PIA) -- the benefit payable if
                                       # claimed exactly at full_retirement_age
                                       # -- not the amount actually paid at
                                       # ss_claim_age.
    full_retirement_age: float | None = None   # NEW
    hdhp_coverage: bool = False
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Consumption expectations for downstream features

- `parse_scenario()` resolves `full_retirement_age` to a concrete `float` when the YAML omits it,
  defaulting to that member's own `ss_claim_age` — so every downstream consumer (`validate()`,
  `retirement_planner.comparison.run_plan_projection()`) always receives a concrete value, never
  `None` (data-model.md, research.md Decision 3).
- This default reproduces every pre-existing scenario's current behavior exactly (zero adjustment,
  `ss_annual_benefit` paid as-is) — no existing scenario YAML file or test fixture needs updating for
  this change alone, mirroring `010-advanced-tax-benefits`'s own precedent for `hdhp_coverage`/
  `hsa_contribution`.
- `retirement_planner.comparison`'s `run_plan_projection()` (`004`) is what interprets
  `full_retirement_age` and the redefined `ss_annual_benefit` together (via the new
  `retirement_planner.mechanics.compute_social_security_benefit()`, see `contracts/mechanics-api.md`
  addendum) — `retirement_planner.scenario` itself only stores and round-trips the field, the same
  precedent `001` already set for `roth_conversion`.
- `services/bff`'s `ScenarioRequest`/`HouseholdMemberRequest` (`007`) gains the same field, mirroring
  this shape exactly (`full_retirement_age: float | None = None`) — see plan.md's Project Structure.
- `validation.py` gains one new **warning**-severity rule (not part of this contract's shape, but
  noted here since it reads this field): a resolved `full_retirement_age` outside `[65.0, 67.0]` is
  flagged as implausible (data-model.md).
