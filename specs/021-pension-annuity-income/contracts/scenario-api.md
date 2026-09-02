# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`, `016`, `017`, `018`)

Extends `specs/017-ss-spousal-survivor-benefits/contracts/scenario-api.md` with one new data type and one additive field. `parse_scenario()`, `validate()`, `save_scenario()`, `list_scenarios()`, `load_scenario()`, `delete_scenario()` keep their existing locked signatures — every existing field of every existing type is unchanged.

## New data type (`models`)

```python
@dataclass
class IncomeStream:
    label: str
    stream_type: Literal["pension", "annuity", "earned_income"]
    start_age: int
    annual_amount: float
    inflation_adjustment: Literal["cola_adjusted", "fixed_nominal"]
    end_age: int | None = None
```

## Modified data type (`models`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float
    full_retirement_age: float | None = None
    hdhp_coverage: bool = False
    predicted_death_age: int | None = None
    income_streams: list[IncomeStream] = field(default_factory=list)   # NEW
```

See [data-model.md](../data-model.md) for field-level meaning; this contract lists shape.

## `parse_scenario()` / `save_scenario()`

- `household.members[*].income_streams` is optional in YAML (defaults to `[]` when the key is omitted, reproducing every pre-existing scenario file's exact current behavior).
- Each entry requires `stream_type`, `start_age`, `annual_amount`, `inflation_adjustment` (`ScenarioParseError` if any is missing — mirrors `_require()`'s existing behavior for other required fields); `end_age` and `label` are optional (`label` defaults to `""` if omitted — display-only, never validated).
- `validate()` gains two new blocking rules, checked per stream (data-model.md § IncomeStream Validation): `end_age < start_age` when `end_age` is set, and `annual_amount < 0`.
- `save_scenario()` round-trips every `IncomeStream` field exactly, the same "found via a real save/load round-trip test" discipline `017`/`018` already established for `predicted_death_age`/`survivor_spending_reduction_pct`.

## Consumption expectations for downstream features

- `retirement_planner.mechanics.income_streams.compute_income_stream_amount()` (see `contracts/mechanics-api.md` addendum) does not take a `HouseholdMember` or `IncomeStream` list at all — it operates on one `IncomeStream` plus caller-supplied age/year context, exactly like `compute_social_security_benefit()` already does with a PIA/FRA pair. `retirement_planner.scenario` itself only stores and round-trips `income_streams` — it plays no role in this feature's own income calculations.
- `services/bff`'s `HouseholdMemberRequest` gains a mirrored `income_streams: list[IncomeStreamRequest] = []` (`schemas.py`) — see plan.md's Project Structure. No `resolution.py` change is needed: `routes/scenarios.py` already converts every `ScenarioRequest` to YAML via `body.model_dump(mode="json")` before calling `parse_scenario()`, so a field-name-matching addition round-trips automatically (research.md §6).
