# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`, `011`)

Extends `specs/001-scenario-config-management/contracts/scenario-api.md` (further extended by `010`'s and `011`'s own contracts) with two additive fields on `Account` and one new data type. `parse_scenario()`, `validate()`, `save_scenario()`, `list_scenarios()`, `load_scenario()`, `delete_scenario()` keep their existing signatures — only `Account`'s shape and `validate()`'s set of possible flags change.

## New data type (`models`)

```python
@dataclass
class InheritedIraDetails:
    death_year: int
    decedent_age_at_death: int
    decedent_was_taking_rmds: bool
    beneficiary_relationship: Literal["spouse", "minor_child", "other_individual", "trust_or_entity"]
    beneficiary_classification: Literal[
        "eligible_designated_beneficiary_spouse",
        "eligible_designated_beneficiary_other",
        "non_eligible_designated_beneficiary",
    ]
```

## Modified data type (`models`)

```python
@dataclass
class Account:
    account_type: Literal["traditional", "roth", "taxable"]
    balance: float
    owner: str | None = None
    account_id: str | None = None                  # NEW — see data-model.md
    inherited: InheritedIraDetails | None = None    # NEW — see data-model.md
```

See [data-model.md](../data-model.md) for field-level meaning and validation rules; this contract lists shape.

## Modified behavior (`loader.parse_scenario`)

- An account entry's `account_id` key is optional in the YAML. When omitted, `_build_account()` assigns `f"{account_type}-{index}"` deterministically, where `index` is that account's zero-based position in `scenario.accounts` (research.md §10) — never a random value.
- An account entry's `inherited` key is optional. When present, every one of `InheritedIraDetails`' five fields is required within that block (parse error, not a validation flag, if any is missing — mirroring `_build_roth_conversion()`'s existing "present block, required inner fields" pattern) — `death_year`, `decedent_age_at_death`, `decedent_was_taking_rmds`, `beneficiary_relationship`, `beneficiary_classification`.
- The public `parse_scenario(yaml_text, *, name=None) -> Scenario` signature is unchanged.

## Modified behavior (`validation.validate`)

`validate()` can now also return, in addition to every existing flag it already produces:

- `ValidationFlag(field="accounts[{i}].inherited", severity="blocking", message=...)` — when `account.inherited is not None and account.inherited.decedent_was_taking_rmds is False`. Names the pre-RBD case as unsupported.
- `ValidationFlag(field="accounts[{i}].inherited", severity="blocking", message=...)` — when `account.inherited is not None and account.inherited.beneficiary_classification != "non_eligible_designated_beneficiary"`. Names the specific EDB/spousal case as unsupported.
- `ValidationFlag(field="accounts[{i}].inherited", severity="blocking", message=...)` — when `account.inherited is not None and account.account_type != "traditional"`. Names the Roth/taxable inherited case as unsupported.
- The existing `accounts[{i}].owner` missing/unmatched-owner checks (`011`) apply unchanged to an inherited account — an inherited account with no `owner` set still produces the same missing-owner flag as any other account.

Every other existing `ValidationFlag` this feature could produce (`001`'s negative-balance/claiming-age/spending-vs-assets checks, `010`'s HSA checks) is unchanged.

## Consumption expectations for downstream features

- `retirement_planner.scenario` (`001`) continues to treat `account_id`/`inherited` as values it stores, round-trips through YAML, and validates for presence/consistency — it does not itself compute or expose anything derived (no per-account runtime balance tracking, no divisor lookups). `services/bff`'s `resolution.py` (`007`, extended by this feature) is what derives `InheritedAccountBalance` instances from `Scenario.accounts` for `004` to consume (data-model.md § Derived).
- A `Scenario` with any inherited-account blocking flag has `is_usable=False` (the existing rule, unchanged) — `004`/`007` callers already refuse to run a comparison/simulation against a non-usable scenario (existing behavior, unchanged by this feature).
- `services/bff`'s `AccountRequest`/`ScenarioRequest` (`007`) gain the same fields, mirroring this shape exactly — see [bff-api.md](./bff-api.md).
