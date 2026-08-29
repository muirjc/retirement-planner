# Contract: `retirement_planner.comparison` public API (addendum to `004`)

Extends `specs/004-strategy-comparison-layer/contracts/comparison-api.md` with one additive field on `StrategyConfiguration`, the `PlanYearProjection`/`PlanOutcome` field additions already listed in [data-model.md](../data-model.md), and one additive optional parameter on 6 of the 7 `compare_*()` functions across `004`/`005-simulation-engine`. `run_plan_projection()` and `run_simulation()` themselves keep their exact locked signatures.

**Correction during planning**: an earlier draft of this design added a new `hsa_contribution` *parameter* directly to `run_plan_projection()`, which would have needed threading through all 8 downstream signatures. Found a simpler fit: `StrategyConfiguration` already carries several fields (`conversion_strategy`, `conversion_bracket_ceiling_or_amount`, `conversion_window`) that most `compare_*()` functions "force" onto every candidate before running — exactly the "held fixed across every candidate" role `hsa_contribution` needs — so `run_plan_projection()`/`run_simulation()` need no change at all; whatever `hsa_contribution` value sits on the `strategy: StrategyConfiguration` they're handed rides straight through.

**Second correction, found during implementation (T027-T028)**: the practical question is which of the 7 `compare_*()` functions (`004`'s 3, `005`'s 4) can rely on that automatic ride-through versus need an explicit new parameter:
- `compare_states` (`005` only) needs **no change** — it already takes a single shared `strategy: StrategyConfiguration` applied identically to every state candidate, so whatever `hsa_contribution` is on it already applies uniformly.
- `compare_roth_conversion_strategies`, `compare_withdrawal_sequencing_strategies` (both `004` and `005`) take `candidates: list[StrategyConfiguration]` and already normalize several fields via `dataclasses.replace(candidate, ...)` before running each one — **each gains one new optional `hsa_contribution: HsaContributionPlan | None = None` parameter**, added to that same `replace()` call, matching the existing explicit-normalization pattern (never silently trusting whatever a candidate already happened to carry, the same discipline already applied to `withdrawal_strategy`/`claiming_ages`).
- `compare_claiming_age_grid` (both `004` and `005`) builds each `StrategyConfiguration` directly from scalar parameters rather than starting from a caller-supplied candidate — it has no existing value to ride through at all, so it also **gains the same new optional parameter**, threaded into the `StrategyConfiguration(...)` it constructs.

Net: 6 of 7 `compare_*()` functions gain one optional, backward-compatible parameter each (default `None`, reproducing every existing call site's behavior unmodified); `compare_states` and both engines' bottom-level `run_plan_projection()`/`run_simulation()` need no change.

## Modified data type

```python
@dataclass
class StrategyConfiguration:
    label: str
    withdrawal_strategy: str
    conversion_strategy: str | None
    conversion_bracket_ceiling_or_amount: float | None
    conversion_window: tuple[int, int] | None
    claiming_ages: dict[str, int]
    hsa_contribution: HsaContributionPlan | None = None   # NEW, optional,
        # defaults to None -- reproduces every existing StrategyConfiguration
        # construction's exact current behavior unmodified
```

## Modified operation

```python
def run_plan_projection(
    household: Household,
    accounts: AccountBalances,
    annual_spending_need: float,
    state: str,
    reference_tax_year: int,
    start_plan_year: int,
    start_tax_year: int,
    plan_to_age: int,
    strategy: StrategyConfiguration,
    return_assumption: DeterministicReturnAssumption,
) -> PlanProjection:
    """Signature UNCHANGED. Behavior extended: each plan year, computes
    that year's IrmaaResult and NiitResult immediately after
    federal_tax/state_tax (using the shared MAGI-approximation helper,
    research.md §2), and, when strategy.hsa_contribution is not None,
    computes that year's HsaContributionResult from household's own
    per-member hdhp_coverage and each member's Medicare-enrollment status
    (age >= 65) and passes it into compute_plan_year_mechanics()
    (FR-008-FR-012)."""
```

## Modified `compare_*()` signatures (6 of 7)

```python
# 004's comparison/compare.py and 005's simulation/compare.py, each:
def compare_roth_conversion_strategies(..., hsa_contribution: HsaContributionPlan | None = None) -> ...
def compare_withdrawal_sequencing_strategies(..., hsa_contribution: HsaContributionPlan | None = None) -> ...
def compare_claiming_age_grid(..., hsa_contribution: HsaContributionPlan | None = None) -> ...

# 005 only -- unchanged, no new parameter (see correction note above):
def compare_states(...) -> ...
```

## Consumption expectations for downstream features

- `services/bff`'s `resolve_run_context()` (`007`) resolves `Scenario.hsa_contribution` into the `StrategyConfiguration` it already builds there (mirroring exactly how it already resolves `Scenario.roth_conversion` into that same object's `conversion_strategy`/`conversion_bracket_ceiling_or_amount`/`conversion_window` fields).
- **Found during implementation (T030)**: resolving it onto `context.strategy` is necessary but not sufficient — `routes/simulations.py`'s single-run path already gets the benefit automatically (it passes `strategy=context.strategy` straight through), but `routes/comparisons.py` builds each comparison candidate independently (via `build_candidates_for_axis()` for the `roth_conversion_strategy`/`withdrawal_sequencing` axes, or a fresh `StrategyConfiguration` per grid cell for `claiming_age_grid`) — none of those start from `context.strategy`, so `hsa_contribution` never reached them without also passing `hsa_contribution=context.strategy.hsa_contribution` explicitly into each of the 6 `compare_*()` calls this module makes (everything except `compare_states`, which already receives it via `strategy=context.strategy`).
