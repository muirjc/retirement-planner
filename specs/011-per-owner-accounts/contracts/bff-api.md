# Contract: `services/bff` HTTP API (addendum to `007`, `010`)

Extends `specs/007-bff-api-service/contracts/bff-api.md` with one additive request field. No route, status code, or response envelope shape changes — `ScenarioResponse` bodies are `to_jsonable()` output (`007`'s own convention: no hand-mirrored response models), so `Account.owner` (`scenario-api.md`, this feature) appears in every existing `GET`/`PUT /scenarios/{name}` and `POST /scenarios/{name}/validate` response automatically, with no serializer change required.

## Modified request schema (`schemas.py`)

```python
class AccountRequest(BaseModel):
    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None   # NEW — mirrors scenario-api.md's Account.owner exactly
```

`ScenarioRequest.accounts: list[AccountRequest]` is otherwise unchanged. A request that omits `owner` behaves exactly as `scenario.loader.parse_scenario()` already does for a YAML file omitting it (single-member household: auto-filled; multi-member: surfaces as a blocking `validation_flags` entry in the response, not a 422 — `PUT`/`POST .../validate` already return `200` with `validation_flags` for every other blocking value-level problem, unchanged by this feature).

## Modified internal resolution (`resolution.py`) — not a wire-contract change, documented for downstream-feature awareness

`resolve_run_context()` (called by `routes/simulations.py` and `routes/comparisons.py`, unchanged HTTP surface) now also computes `traditional_ownership_shares: dict[str, float]` from the resolved `Scenario.accounts` (data-model.md § Derived) and adds it to `ResolvedRunContext`, alongside the existing `accounts: AccountBalances`. Every call this module makes into `retirement_planner.comparison`/`retirement_planner.simulation` (`run_plan_projection()`, `run_simulation()`, every `compare_*()`) passes it through, per `comparison-api.md`/`simulation-api.md`'s new required parameter.

## Consumption expectations for downstream features

- A future second UI (`008`'s own contract note, unchanged) builds its account-entry form against `AccountRequest.owner` exactly as it already builds against every other `AccountRequest` field — nothing about this field is Streamlit-specific.
- `POST /scenarios/{name}/validate` is the one endpoint a UI should call to surface an owner-related blocking flag *before* a user attempts to run a simulation or comparison against a scenario that isn't usable yet (existing `007` pattern, unchanged) — `routes/simulations.py`/`routes/comparisons.py` already refuse a non-`is_usable` scenario (existing behavior, unaffected by this feature, per `scenario-api.md`'s note above).
