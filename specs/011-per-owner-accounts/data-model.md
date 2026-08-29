# Data Model: Per-Owner Account Attribution

Source: [spec.md](./spec.md) Key Entities section, resolved by [research.md](./research.md). This feature modifies one existing entity (`Account`, `001`) and introduces one new derived value (`traditional_ownership_shares`, computed by `007`, consumed by `004`/`005`) — it defines no new persisted entity. Types are described conceptually; the locked contracts for downstream features are in [contracts/](./contracts/).

## Account (modified — `001`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `account_type` | enum: `traditional`, `roth`, `taxable` | yes | Unchanged. |
| `balance` | number (currency) | yes | Unchanged. |
| `owner` | string \| null | **NEW** — see Validation rules | References a `household.members[*].person_name`. `None` only ever appears transiently, mid-parse, before validation runs (research.md §3) — a `Scenario` that has passed validation with `is_usable=True` never has an `owner=None` account. |

**Validation rules** (new, in `scenario.validation.validate()`):
- `owner is None` and `len(household.members) > 1` → blocking `ValidationFlag` (`accounts[i].owner`, "Account is missing an owner — choose one of: {member names}"). `validate()` checks household size itself — it does not rely on `scenario.loader.parse_scenario()` having already auto-filled the sole member for a single-member household (FR-003); a `Scenario` built directly (as most of this codebase's own test fixtures already do, bypassing the loader) is just as unambiguous for a single member and must validate cleanly either way.
- `owner is not None` and does not equal any `household.members[*].person_name` → blocking `ValidationFlag` (`accounts[i].owner`, "Account owner '{owner}' does not match any household member — known members: {member names}"). Fires for any household size, covering a typo or a stale reference after a member rename (Edge Cases).

**Parse-time behavior** (`scenario.loader.parse_scenario()`, structural — not a `ValidationFlag`):
- Household is now built before accounts are built (an ordering change from `001`'s current implementation, where account-building doesn't need the household yet) so `_build_account()` can consult `household.members` for the single-member auto-fill.
- `owner` is read permissively (`data.get("owner")`, no `_require()`) — a missing key never raises `ScenarioParseError`, regardless of household size; only `validate()` (above) surfaces a problem for the multi-member case.

**Relationships** (updated): A `Scenario`'s `accounts` are no longer household-anonymous — each now references exactly one of that same `Scenario`'s `household.members`. No `Account` may reference a member outside its own `Scenario` (there is no cross-`Scenario` reference of any kind, unchanged from `001`).

## HouseholdMember (unchanged — `001`)

No field changes. `person_name` is now also the value every `Account.owner` in the same `Scenario` is validated against — its existing "free text" contract (data-model.md, `001`) is unchanged, but it is now compared for equality against `Account.owner` strings, so two members sharing an identical `person_name` within one household would make ownership ambiguous. This is not newly introduced by this feature — `001`'s existing schema already permits two members with the same `person_name` and never disambiguated them for any other purpose either; this feature does not add a uniqueness rule that didn't already implicitly need to hold for a well-formed household, and does not regress anything that worked before (the reference scenario and every existing test fixture use distinct names).

## Derived: `traditional_ownership_shares` (new — computed by `007`, consumed by `004`/`005`)

Not a persisted or user-authored entity — a plain `dict[str, float]` computed once per resolved run (`services/bff/src/rp_bff/resolution.py`) from a `Scenario`'s `accounts`, and threaded as a required parameter through `run_plan_projection()` (`004`), `run_simulation()` and every `simulation.compare_*()` (`005`), and every `comparison.compare_*()` (`004`).

| Key | Value | Notes |
|---|---|---|
| `person_name` (one entry per `household.members`) | float, `0.0`–`1.0` | That member's share of the household's *initial* pooled traditional balance: `sum(account.balance for account in scenario.accounts if account.account_type == "traditional" and account.owner == person_name) / household_initial_traditional_total`. All entries sum to `1.0` when `household_initial_traditional_total > 0`; all entries are `0.0` when it is `0.0` (research.md §2). |

**Validation rules**: None inside the compute layer (`004`/`005` trust this dict as pre-resolved input, matching how they already trust `AccountBalances`/`Household` — research.md §2) — `run_plan_projection()` raises `KeyError` eagerly if any `household.members[*].person_name` is missing as a key, mirroring `005`'s existing `survival_curves` precedent (FR-018).

**Relationships**: Computed once per run, from one `Scenario`'s `accounts` and `household.members` — held fixed for the entire multi-year projection it's used in (research.md §1); never recomputed mid-projection, never derived from a running/mutated balance.

## Consumption: RMD computation inside `run_plan_projection()` (modified — `004`)

Replaces the current single `deemed_rmd_owner()`-attributed `compute_rmd()` call with one `compute_rmd()` call per household member whose `traditional_ownership_shares[person_name] > 0` (skipping a `0.0`-share member is a pure optimization — `compute_rmd()` already returns a zero result for a non-positive balance either way):

- Each member's own traditional balance for the plan year = `traditional_ownership_shares[member.person_name] * current_balances.traditional`.
- Each member's own age = `member_age_in_tax_year(member, tax_year, reference_tax_year)` (unchanged helper, `004`/`006`).
- `spouse_age`/`spouse_is_sole_beneficiary` arguments to `compute_rmd()` are passed exactly as today (unchanged — research.md §3 in `004`'s own research.md: always Uniform Lifetime Table, `spouse_is_sole_beneficiary=False`; this feature does not revisit that separate, still-open simplification).
- The plan year's total `rmd_amount` (fed into `compute_plan_year_mechanics()`, unchanged downstream) = the sum of every member's individually-computed `required_amount`. `figures_used` is the union across all member-level `compute_rmd()` calls (was previously the union across one call — the union pattern itself is unchanged).

`deemed_rmd_owner()` itself is retained, unmodified, for `006`'s unrelated age-labeling use (research.md §4) — it is simply no longer called from this RMD-sizing path.
