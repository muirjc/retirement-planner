# Contract: `retirement_planner.scenario` public API

This is a library, not a network service — the "contract" is the public Python interface that this feature exposes for later features (tax engine, strategy layer, simulation engine, reporting) to import and build on. Anything not listed here is an internal implementation detail and may change without notice; anything listed here is what downstream features should code against.

Module: `retirement_planner.scenario` (re-exports from `models`, `loader`, `store`, `validation` — see [plan.md](../plan.md) Project Structure).

## Data types (`models`)

```python
@dataclass
class HouseholdMember:
    person_name: str
    current_age: int
    ss_claim_age: int
    ss_annual_benefit: float

@dataclass
class Household:
    filing_status: Literal["single", "married_filing_jointly"]
    members: list[HouseholdMember]

@dataclass
class Account:
    account_type: Literal["traditional", "roth", "taxable"]
    balance: float

@dataclass
class SpendingProfile:
    annual_need_real: float

@dataclass
class RothConversionPlan:
    strategy: str
    bracket_ceiling_or_amount: float
    window: tuple[int, int]

@dataclass
class MarketAssumptions:
    equity_allocation: float
    equity_return_mean_real: float
    equity_return_std_real: float
    bond_allocation: float
    bond_return_mean_real: float
    bond_return_std_real: float
    correlation: float

@dataclass
class SimulationSettings:
    n_paths: int
    seed: int
    plan_to_age: int

@dataclass
class ValidationFlag:
    field: str
    message: str
    severity: Literal["blocking", "warning"]

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
    validation_flags: list[ValidationFlag] = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """True iff no `blocking` flag is present (`warning`-only or empty is usable)."""
```

See [data-model.md](../data-model.md) for field-level validation rules; this contract lists shape, not rules.

## Errors (`loader`)

```python
class ScenarioParseError(Exception):
    """Raised when a config file cannot be parsed into a Scenario shape at all
    (malformed YAML, wrong household member count for filing_status, wrong
    types). Distinct from a value-level validation problem — see FR-012."""
    def __init__(self, source: str, reason: str): ...
```

Callers MUST distinguish `ScenarioParseError` (file couldn't be turned into a `Scenario` at all) from a successfully-parsed `Scenario` whose `validation_flags` contains `blocking` entries (parsed fine, but contains impossible values). Both ultimately mean "not usable downstream," but the message/handling differs per FR-012.

## Operations (`loader`, `store`, `validation`)

```python
def parse_scenario(yaml_text: str, *, name: str | None = None) -> Scenario:
    """Parse raw YAML text into a Scenario. Does NOT run validate() —
    callers combine parse + validate themselves, or use load_scenario()
    below, which does both. Raises ScenarioParseError on malformed input."""

def validate(scenario: Scenario) -> list[ValidationFlag]:
    """Run every validation rule in data-model.md against `scenario` and
    return every problem found (FR-006) — never stops at the first one.
    Does not mutate `scenario`; callers assign the result to
    `scenario.validation_flags` themselves (load_scenario() does this)."""

def save_scenario(scenario: Scenario) -> None:
    """Persist `scenario` under `scenario.name`, overwriting any existing
    saved scenario of the same name (FR-015). Does not require the
    scenario to be valid — an author may save a work-in-progress scenario
    with blocking flags and come back to fix it later."""

def list_scenarios() -> list[str]:
    """Return every saved scenario name (FR-004), in a stable (e.g.,
    alphabetical) order."""

def load_scenario(name: str) -> Scenario:
    """Load the named scenario, parse it, and populate its
    validation_flags (i.e., parse_scenario() + validate() combined).
    Raises ScenarioParseError if the named scenario's file doesn't exist
    or can't be parsed. Callers check `.is_usable` / `.validation_flags`
    themselves to decide whether to proceed — load_scenario() never
    raises merely because of a blocking ValidationFlag; only a
    ScenarioParseError blocks the call itself, per FR-012 vs FR-006/014."""
```

## Consumption expectations for downstream features

- The tax engine, strategy layer, and simulation engine features MUST treat `Scenario.roth_conversion` and `Scenario.state` as opaque values they interpret themselves — this feature does not validate them against any implemented tax/strategy module (see spec Edge Cases).
- Any downstream feature that needs a *new* scenario field MUST add it to `models.py` and `data-model.md` rather than smuggling extra keys through an untyped dict, per FR-002 ("one consistent, named structure").
- `ValidationFlag.severity == "blocking"` is the single signal downstream features should check before running expensive computation (simulation, tax calculation) against a `Scenario` — via `Scenario.is_usable`.
