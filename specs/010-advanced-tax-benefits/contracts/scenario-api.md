# Contract: `retirement_planner.scenario` public API (addendum to `001`)

Extends `specs/001-scenario-config-management/contracts/scenario-api.md` with two additive fields. Everything else in that contract — `parse_scenario()`, `validate()`, `save_scenario()`, `list_scenarios()`, `load_scenario()`, `delete_scenario()`, and every other existing field — is unchanged.

## Modified data types (`models`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    hdhp_coverage: bool = False   # NEW

@dataclass
class HsaContributionPlan:        # NEW
    annual_amount: float

@dataclass
class Scenario:
    name: str
    household: Household
    accounts: list[Account]
    spending: SpendingProfile
    state: str
    market_assumptions: MarketAssumptions
    simulation_settings: SimulationSettings
    roth_conversion: RothConversionPlan | None = None
    hsa_contribution: HsaContributionPlan | None = None   # NEW
    validation_flags: list[ValidationFlag] = field(default_factory=list)

    @property
    def is_usable(self) -> bool: ...  # unchanged
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## Consumption expectations for downstream features

- `retirement_planner.scenario` (`001`) treats `hdhp_coverage` and `hsa_contribution` as opaque values it stores and round-trips through YAML but does not itself validate beyond shape — the same precedent `001` already set for `roth_conversion` (`specs/001-scenario-config-management/contracts/scenario-api.md`'s own note: downstream features interpret `roth_conversion`/`state` themselves). `retirement_planner.comparison`'s `run_plan_projection()` (`004`, extended by this feature) is what interprets both.
- Both fields default to values that reproduce every existing `Scenario`'s exact current behavior — no `001` change is required to any already-saved scenario YAML file, and no existing test fixture needs updating for this change alone.
- `services/bff`'s `ScenarioRequest` (`007`) gains the same two fields, mirroring this shape exactly, so a scenario built through the HTTP API can express them — see plan.md's Project Structure.
