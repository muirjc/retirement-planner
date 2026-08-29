# Contract: `services/bff` HTTP API (addendum to `007`, `010`, `011`)

Extends `specs/007-bff-api-service/contracts/bff-api.md` with two additive request fields, no route/response-shape change for scenario endpoints, and one new rejection case for `POST /simulations` and the simulated branch of `POST /comparisons`.

## Modified request schema (`schemas.py`)

```python
class InheritedIraDetailsRequest(BaseModel):
    death_year: int
    decedent_age_at_death: int
    decedent_was_taking_rmds: bool
    beneficiary_relationship: Literal["spouse", "minor_child", "other_individual", "trust_or_entity"]
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ]


class AccountRequest(BaseModel):
    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None
    account_id: str | None = None                              # NEW — mirrors scenario-api.md's Account.account_id
    inherited: InheritedIraDetailsRequest | None = None         # NEW — mirrors scenario-api.md's Account.inherited
```

`ScenarioRequest.accounts: list[AccountRequest]` is otherwise unchanged. A request that omits `account_id` behaves exactly as `scenario.loader.parse_scenario()` already does for an omitted YAML key (deterministic auto-fill, never a 422). A request whose `inherited` block encodes an unsupported case (pre-RBD, EDB, non-traditional) behaves exactly as every other blocking value-level problem already does — it surfaces as a `validation_flags` entry in the `PUT`/`POST .../validate` response body, not a 422 (`007`'s existing convention, unchanged).

## Modified internal resolution (`resolution.py`) — not a wire-contract change for scenario endpoints, documented for downstream-feature awareness

`resolve_run_context()` (called by `routes/simulations.py` and `routes/comparisons.py`, unchanged HTTP surface for scenario/account endpoints) now also computes `inherited_accounts: list[InheritedAccountBalance]` from the resolved `Scenario.accounts` (data-model.md § Derived, excluding these same accounts from `accounts`/`traditional_ownership_shares`'s pooled totals — data-model.md § Exclusion from pooling) and adds it to `ResolvedRunContext`:

```python
@dataclass
class ResolvedRunContext:
    scenario: Scenario
    household: Household
    accounts: AccountBalances
    traditional_ownership_shares: dict[str, float]
    inherited_accounts: list[InheritedAccountBalance]   # NEW
    strategy: StrategyConfiguration
    state: str
    plan_to_age: int
    n_paths: int
    seed: int
```

Every deterministic-comparison call this module makes into `retirement_planner.comparison` (`run_plan_projection()` — not currently called directly by any route; every `compare.py` function) passes `inherited_accounts` through, per `comparison-api.md`'s new parameter — each call site constructs a fresh, independently-copied list per candidate (comparison-api.md's own note), never reusing `context.inherited_accounts`' own instances directly across more than one candidate.

## New rejection: Monte Carlo requests against a scenario with inherited accounts

```python
class InheritedAccountsUnsupportedForSimulationError(Exception):
    """Raised by resolve_and_run_simulation() (routes/simulations.py) and
    the simulated-comparison resolve path (routes/comparisons.py) when
    ResolvedRunContext.inherited_accounts is non-empty (research.md §10
    addendum) -- Monte Carlo threading is explicit follow-on work, not
    silently unsupported."""
```

`routes/simulations.py`'s `resolve_and_run_simulation()` and `routes/comparisons.py`'s simulated-comparison resolve path each check `context.inherited_accounts` immediately after a successful `resolve_run_context()` call and raise this exception if it is non-empty — translated, at the route level, into:

```json
HTTP 422
{
  "error": "inherited_accounts_unsupported_for_simulation",
  "account_ids": ["traditional-1", "traditional-2"]
}
```

`POST /simulations`, and the simulated branch of `POST /comparisons` (i.e. a request whose `mode`/equivalent selects Monte Carlo rather than deterministic), are the only two endpoints affected. `POST /comparisons`' deterministic branch, and any endpoint that resolves a context without calling `run_simulation()`/`simulation.compare_*()` (e.g. `POST /scenarios/{name}/validate`), are unaffected — a scenario with an inherited account remains fully usable through every deterministic endpoint.

## Consumption expectations for downstream features

- A future UI build against `AccountRequest.account_id`/`.inherited` exactly as it already builds against every other `AccountRequest` field — nothing about these fields is Streamlit-specific; this feature itself does not build that UI (research.md §9.9, plan.md's Structure Decision).
- `POST /scenarios/{name}/validate` is the one endpoint a UI should call to surface an inherited-account blocking flag *before* a user attempts to run a simulation or comparison against a scenario that isn't usable yet (existing `007` pattern, unchanged).
- A UI (or any BFF client) that receives the `422 inherited_accounts_unsupported_for_simulation` response should offer the deterministic single-projection/comparison endpoints as the supported path for a scenario with inherited accounts, until a follow-on feature removes this restriction.
