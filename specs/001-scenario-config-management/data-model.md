# Data Model: Scenario Configuration & Validation

Source: [spec.md](./spec.md) Key Entities section, resolved against the Assumptions and Clarifications (FR-014–FR-016). Types are described conceptually (Python `dataclasses`, per [research.md](./research.md) §1) — field names are illustrative, not a locked contract; the locked contract for downstream features is [contracts/scenario-api.md](./contracts/scenario-api.md).

## Scenario

The top-level, named unit of input data. One YAML file = one `Scenario`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | User-chosen identifier; also the storage key (FR-003). Must be filesystem-safe. |
| `household` | Household | yes | |
| `accounts` | list[Account] | yes | At least one account entry (traditional, Roth, or taxable), per reference use case. |
| `spending` | SpendingProfile | yes | |
| `roth_conversion` | RothConversionPlan | no | Opaque reference for a future strategy-layer feature (Assumptions); absent = "no conversion plan configured." |
| `state` | string | yes | State-of-residence code (e.g., `"GA"`). Stored as a plain reference value — this feature does not validate it against implemented tax modules (Edge Cases). |
| `market_assumptions` | MarketAssumptions | yes | |
| `simulation_settings` | SimulationSettings | yes | |
| `validation_flags` | list[ValidationFlag] | derived | Populated by `validate()`, not authored by the user. Empty list = no problems found. |

**Relationships**: A `Scenario` owns exactly one `Household`, one `SpendingProfile`, one `MarketAssumptions`, one `SimulationSettings`, zero or one `RothConversionPlan`, and one-or-more `Account`s. `Scenario` is the unit of save/list/load isolation (FR-005) — no entity is shared by reference across two `Scenario`s.

## Household

| Field | Type | Required | Notes |
|---|---|---|---|
| `filing_status` | enum: `single`, `married_filing_jointly` | yes | Determines whether 1 or 2 `HouseholdMember`s are expected (FR-013). |
| `members` | list[HouseholdMember] | yes | Length 1 (single) or 2 (MFJ). |

**Validation rules**: `len(members)` must match `filing_status` (1 for single, 2 for MFJ) — malformed otherwise (FR-012-adjacent structural check, enforced at load/parse time, not as a blocking `ValidationFlag`, since it's a shape error rather than a value-plausibility error).

## HouseholdMember

| Field | Type | Required | Notes |
|---|---|---|---|
| `person_name` | string | yes | Free text (e.g., `"you"`, `"spouse"`, or a real name). |
| `current_age` | integer | yes | |
| `ss_claim_age` | integer | yes | Must be 62–70 inclusive (FR-008). |
| `ss_annual_benefit` | number (currency) | yes | Non-negative. |

**Validation rules**:
- `ss_claim_age` outside [62, 70] → blocking `ValidationFlag` (FR-008).
- `ss_annual_benefit` < 0 → blocking `ValidationFlag` (FR-007).

## Account

| Field | Type | Required | Notes |
|---|---|---|---|
| `account_type` | enum: `traditional`, `roth`, `taxable` | yes | |
| `balance` | number (currency) | yes | |

**Validation rules**: `balance` < 0 → blocking `ValidationFlag`, field identified as `accounts[<type>].balance` (FR-007, FR-011).

## SpendingProfile

| Field | Type | Required | Notes |
|---|---|---|---|
| `annual_need_real` | number (currency) | yes | Today's-dollars annual spending need. |

**Validation rules**:
- `annual_need_real` < 0 → blocking `ValidationFlag` (FR-007).
- `annual_need_real` == 0 → allowed, no flag (Edge Cases: zero is plausible).
- `annual_need_real * plan_horizon_years > total_starting_assets` (horizon derived from `simulation_settings.plan_to_age` minus the older member's `current_age`; assets summed across all `accounts`) → warning `ValidationFlag`, scenario still loads (FR-009, FR-014).

## RothConversionPlan *(optional)*

| Field | Type | Required | Notes |
|---|---|---|---|
| `strategy` | string | yes, if present | Opaque reference (e.g., `"fill_to_bracket"`) — not validated against implemented strategies by this feature (Edge Cases; Assumptions). |
| `bracket_ceiling_or_amount` | number | yes, if present | Stored as-is; interpretation belongs to the future strategy-layer feature. |
| `window` | tuple[int, int] (start year, end year) | yes, if present | Stored as-is; no cross-field validation against other dates in this feature. |

## MarketAssumptions

| Field | Type | Required | Notes |
|---|---|---|---|
| `equity_allocation` | number (0–1) | yes | |
| `equity_return_mean_real` | number | yes | |
| `equity_return_std_real` | number | yes | |
| `bond_allocation` | number (0–1) | yes | |
| `bond_return_mean_real` | number | yes | |
| `bond_return_std_real` | number | yes | |
| `correlation` | number (-1–1) | yes | |

**Validation rules**: None beyond required-field presence in this feature — these values are only consumed (interpreted, range-checked for simulation purposes) by the future simulation-engine feature.

## SimulationSettings

| Field | Type | Required | Notes |
|---|---|---|---|
| `n_paths` | integer | yes | |
| `seed` | integer | yes | |
| `plan_to_age` | integer | yes | Used to derive the plan horizon for the spending-vs-assets plausibility check (`SpendingProfile` validation rules, above). |

**Validation rules**: None beyond required-field presence in this feature (simulation-scale/performance concerns belong to the future simulation-engine feature).

## ValidationFlag *(derived, not authored)*

| Field | Type | Notes |
|---|---|---|
| `field` | string | Dotted path to the offending field (e.g., `"household.members[1].ss_claim_age"`), per FR-011. |
| `message` | string | Plain-language reason, per FR-011. |
| `severity` | enum: `blocking`, `warning` | `blocking` = impossible value or unparseable file (scenario unusable downstream); `warning` = plausibility concern (scenario still usable), per FR-014. |

## State transitions

This feature has no multi-step lifecycle beyond simple CRUD-like operations — a `Scenario` is authored, saved, listed, loaded, and validated; there is no draft/approved/archived status model (per FR-016, no revision history is kept). The only "state" of note is a `Scenario`'s validation outcome (has blocking flags / has only warning flags / has no flags), which is recomputed fresh on every load rather than persisted.
