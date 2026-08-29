# Data Model: Inherited IRA (Already-in-RMD-Status) Modeling

Source: [spec.md](./spec.md) Key Entities section, resolved by [research.md](./research.md). This feature modifies one existing entity (`Account`, `001`), introduces one new persisted entity (`InheritedIraDetails`), and introduces one new derived value (`InheritedAccountBalance`, computed by `007`, consumed by `004`). Types are described conceptually; the locked contracts for downstream features are in [contracts/](./contracts/).

## Account (modified — `001`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `account_type` | enum: `traditional`, `roth`, `taxable` | yes | Unchanged. |
| `balance` | number (currency) | yes | Unchanged. For an inherited account, this is that account's own balance — never pooled with any other account (research.md §5). |
| `owner` | string \| null | yes (see `011`) | Unchanged meaning: the *beneficiary's* `household.members[*].person_name` for an inherited account (research.md §4) — an inherited account is never ownerless. |
| `account_id` | string \| null | **NEW** | A stable per-account handle, used only to key an inherited account's independently-tracked runtime state through a projection (research.md §8). Optional in YAML; `scenario.loader._build_account()` assigns `f"{account_type}-{index}"` deterministically when omitted (research.md §10) — every `Account` has a non-null `account_id` once parsed, whether or not it is inherited. |
| `inherited` | `InheritedIraDetails` \| null | **NEW** | `None` for an ordinary, owner-held account (every existing scenario file). Present only for an account whose original owner has died and whose current `owner` is the beneficiary (research.md §4). |

## InheritedIraDetails (new — `012`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `death_year` | integer (calendar year) | yes | The year the original owner died. Anchors both the annual-distribution divisor schedule and `depletion_deadline_year = death_year + 10` (research.md §7, §8). |
| `decedent_age_at_death` | integer | yes | The original owner's age in `death_year`. Looks up the initial Single Life Expectancy divisor (research.md §7). |
| `decedent_was_taking_rmds` | boolean | yes | `True` — the only value this feature computes (research.md §2) — means the original owner had already reached their Required Beginning Date at death. `False` ("pre-RBD") is recorded but blocked, never computed (see Validation rules). |
| `beneficiary_relationship` | enum: `spouse`, `minor_child`, `other_individual`, `trust_or_entity` | yes | Descriptive/audit metadata (research.md §3). Does not itself drive computation. |
| `beneficiary_classification` | enum: `eligible_designated_beneficiary_spouse`, `eligible_designated_beneficiary_other`, `non_eligible_designated_beneficiary` | yes | What the RMD compute layer branches on (research.md §3). Only `non_eligible_designated_beneficiary` is computed; the two EDB values are recorded but blocked (see Validation rules). |

**Relationships**: One `InheritedIraDetails` belongs to exactly one `Account` (`Account.inherited`), which belongs to exactly one `Scenario`'s `accounts` list. It never references a `HouseholdMember` directly — the decedent is not represented as a household member at all (research.md §1); the beneficiary is reached through the owning `Account.owner`.

## Validation rules (new, in `scenario.validation._validate_accounts()`)

Four new blocking `ValidationFlag`s, each following the existing per-account-index pattern (`field=f"accounts[{index}].inherited"`, or `.owner` for the third, reusing the exact field name `011`'s existing owner check already uses):

| # | Condition | Severity | Message intent |
|---|---|---|---|
| 1 | `account.inherited is not None and account.inherited.decedent_was_taking_rmds is False` | blocking | Names the pre-RBD case as unsupported (research.md §2). |
| 2 | `account.inherited is not None and account.inherited.beneficiary_classification != "non_eligible_designated_beneficiary"` | blocking | Names the specific EDB/spousal case as unsupported (research.md §3). |
| 3 | `account.inherited is not None and account.owner is None` | blocking | An inherited account still needs a beneficiary `owner` — reuses `011`'s existing missing-owner check and message, since this condition already triggers it; no new message needed, just confirmation it still fires for an inherited account (research.md §6). |
| 4 | `account.inherited is not None and account.account_type != "traditional"` | blocking | Names Roth/taxable inherited accounts as unsupported (research.md §10). |

These are checked in addition to, not instead of, every existing `_validate_accounts()` rule (negative balance, missing/unknown owner) — an inherited account is still a full `Account` and gets every ordinary check too.

## Derived: `InheritedAccountBalance` (new — computed by `007`, consumed by `004`)

Not a persisted or user-authored entity — a plain runtime dataclass, one instance built per inherited `Account` once per resolved run (`services/bff/src/rp_bff/resolution.py`), collected into `inherited_accounts: list[InheritedAccountBalance]` and threaded as a new parameter into `run_plan_projection()` (`004`). Unlike `traditional_ownership_shares` (`011`), this is *mutable* runtime state — each instance's `balance` is decremented year-by-year, in place, as `run_plan_projection()` iterates (research.md §8, §10).

| Field | Type | Notes |
|---|---|---|
| `account_id` | string | Copied from the source `Account.account_id`. Used only for correlating this instance back to its source account (e.g., in reporting); never compared for equality against anything else at compute time. |
| `balance` | float | That account's current balance. Starts at `Account.balance`; mutated by `run_plan_projection()` each plan year (distribution subtracted, then growth applied) — never touches, and is never touched by, `AccountBalances.traditional` (research.md §5). |
| `death_year` | integer | Copied from `InheritedIraDetails.death_year`. |
| `decedent_age_at_death` | integer | Copied from `InheritedIraDetails.decedent_age_at_death`. |
| `depletion_deadline_year` | integer | `death_year + 10`, computed once when this instance is built, held fixed for the life of the projection (research.md §8). |

**Construction**: `resolution.py` builds one `InheritedAccountBalance` per `Account` with `inherited is not None`, from a `Scenario` already confirmed `is_usable` — so every source account is guaranteed `account_type == "traditional"`, `inherited.decedent_was_taking_rmds is True`, `inherited.beneficiary_classification == "non_eligible_designated_beneficiary"`, and `owner`/`account_id` both non-null (the four blocking rules above already reject every other case before this point is reached).

**Exclusion from pooling**: An `Account` with `inherited is not None` is excluded from `_sum_accounts()`'s `AccountBalances` totals and from `_traditional_ownership_shares()`'s per-member shares (research.md §5) — it contributes to neither the household's pooled `traditional` total nor any member's ownership-share numerator/denominator.

## Consumption: RMD and distribution computation inside `run_plan_projection()` (modified — `004`)

Each plan year, in addition to the existing per-member `compute_rmd()` calls (`011`), `run_plan_projection()` now also iterates `inherited_accounts`. For each `InheritedAccountBalance` with `balance > 0` and `tax_year <= depletion_deadline_year`:

- If `tax_year == depletion_deadline_year`: that year's distribution is the account's entire remaining `balance` (full forced depletion — research.md §8).
- Otherwise: distribution = `min(compute_inherited_rmd(inherited_balance=balance, tax_year=tax_year, death_year=death_year, decedent_age_at_death=decedent_age_at_death, decedent_was_taking_rmds=True, beneficiary_classification="non_eligible_designated_beneficiary").required_amount, balance)` — the two literal arguments are hardcoded at this call site, exactly mirroring how `compute_rmd()`'s own `spouse_is_sole_beneficiary=False` is already hardcoded immediately above it, both guaranteed by the validation rules above rather than re-derived here.
- The account's `balance` is reduced by the distribution amount immediately (before growth is applied).
- After every inherited account for the year is processed, each surviving (`tax_year < depletion_deadline_year`) account's `balance` is grown by the same `growth_factor` already computed for the household's pooled balances that year (research.md §10) — a deadline-year account's `balance` is already `0.0` and growth on `0.0` is a no-op either way.
- The total of all this year's inherited distributions, and the union of every `compute_inherited_rmd()` call's `figures_used`, are passed into `compute_withdrawal_plan()`/`compute_plan_year_mechanics()` as the new `inherited_distribution_amount`/`inherited_rmd_figures_used` parameters (research.md §10) — reduces `remaining_need` exactly like `rmd_drawn` already does, and folds into `ordinary_income_established` and the year's `figures_used` union the same way.

`inherited_accounts` defaults to `[]` for `run_plan_projection()`'s existing callers, reproducing every current scenario's exact output unchanged when no inherited account is present. Every function in `comparison/compare.py` gains the identical parameter, forwarded to each of its own `run_plan_projection()` calls as an independently-copied list per candidate (contracts/comparison-api.md). `retirement_planner.simulation` (`005`) is not extended by this feature — `services/bff` instead rejects a Monte Carlo simulation or simulated-comparison request against a scenario with any inherited account (contracts/bff-api.md), rather than silently running one that would drop those accounts' distributions.
