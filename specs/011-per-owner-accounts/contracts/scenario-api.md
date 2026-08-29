# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`)

Extends `specs/001-scenario-config-management/contracts/scenario-api.md` (further extended by `specs/010-advanced-tax-benefits/contracts/scenario-api.md`) with one additive-but-enforced field. `parse_scenario()`, `validate()`, `save_scenario()`, `list_scenarios()`, `load_scenario()`, `delete_scenario()` keep their existing signatures — only `Account`'s shape and `validate()`'s set of possible flags change.

## Modified data types (`models`)

```python
@dataclass
class Account:
    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None   # NEW — see data-model.md
```

See [data-model.md](../data-model.md) for field-level meaning and validation rules; this contract lists shape.

## Modified behavior (`loader.parse_scenario`)

- Household is parsed before accounts (ordering change, internal — the public `parse_scenario(yaml_text, *, name=None) -> Scenario` signature is unchanged).
- An account entry's `owner` key is optional in the YAML at parse time (never raises `ScenarioParseError` for being absent, for any household size).
- When `household.members` has exactly one entry, every account's `owner` is set to that member's `person_name` if the YAML omitted it — regardless of what (if anything) the YAML provided otherwise for a single-member household's account (data-model.md § Account, Parse-time behavior).

## Modified behavior (`validation.validate`)

`validate()` can now also return:
- `ValidationFlag(field="accounts[{i}].owner", severity="blocking", message="Account is missing an owner — choose one of: {member names}")` — only when `len(household.members) > 1`; `validate()` checks this itself rather than trusting that `parse_scenario()` already ran (data-model.md § Account).
- `ValidationFlag(field="accounts[{i}].owner", severity="blocking", message="Account owner '{owner}' does not match any household member — known members: {member names}")` — any household size.

Every other existing `ValidationFlag` this feature could produce (`001`'s negative-balance/claiming-age/spending-vs-assets checks, `010`'s HSA checks) is unchanged.

## Consumption expectations for downstream features

- `retirement_planner.scenario` (`001`) continues to treat `owner` as a value it stores, round-trips through YAML, and validates for presence/referential match — it does not itself compute or expose anything derived from ownership (no summed shares, no per-owner totals). `services/bff`'s `resolution.py` (`007`, extended by this feature) is what derives `traditional_ownership_shares` from `Scenario.accounts` for `004`/`005` to consume (data-model.md § Derived).
- A `Scenario` with any `owner=None` or unmatched-`owner` account has `is_usable=False` (the existing `blocking`-flag rule, unchanged) — `004`/`005`/`007` callers already refuse to run a comparison/simulation against a non-usable scenario (existing behavior, unchanged by this feature).
- `services/bff`'s `AccountRequest`/`ScenarioRequest` (`007`) gain the same field, mirroring this shape exactly — see [bff-api.md](./bff-api.md).
