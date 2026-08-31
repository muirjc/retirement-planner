# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`, `016`)

Extends `specs/016-ss-claiming-age-actuarial-adjustment/contracts/scenario-api.md` (itself extending
`001`/`010`) with one additive field. `parse_scenario()`, `validate()`, `save_scenario()`,
`list_scenarios()`, `load_scenario()`, `delete_scenario()`, and every other existing field are
unchanged in shape.

## Modified data types (`models`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    full_retirement_age: float | None = None
    hdhp_coverage: bool = False
    predicted_death_age: int | None = None   # NEW
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Consumption expectations for downstream features

- `predicted_death_age` defaults to `None` and is round-tripped by `parse_scenario()`/
  `save_scenario()` like any other optional field — no defaulting/resolution logic is needed the way
  `full_retirement_age`'s None-to-`ss_claim_age` default requires (016), since `None` here already
  *is* this field's fully-meaningful "no hypothetical death configured" value, consulted by nothing in
  this feature.
- `retirement_planner.mechanics.compute_spousal_benefit_floor()` and `compute_survivor_benefit()`
  (see `contracts/mechanics-api.md` addendum) do not take a `HouseholdMember` at all — they operate on
  raw PIA/benefit floats a caller has already extracted, exactly like `compute_social_security_benefit()`
  already does. `retirement_planner.scenario` itself only stores and round-trips
  `predicted_death_age` — it plays no role in this feature's own calculations.
- `services/bff`'s `HouseholdMemberRequest` (`007`) gains the same field, mirroring this shape exactly
  (`predicted_death_age: int | None = None`) — see plan.md's Project Structure.
- `validation.py` gains two new rules (not part of this contract's shape, but noted here since they
  read this field): a **blocking** rule when `predicted_death_age < current_age` (incoherent), and a
  **warning** rule when a non-`None` `predicted_death_age` falls outside `[50, 110]` (implausible) —
  data-model.md.
- No downstream feature besides `rp-g8y` is expected to read this field yet — it is added now purely
  so that future feature is additive against an already-stable `HouseholdMember` shape.
