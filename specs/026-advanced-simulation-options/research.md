# Phase 0 Research: Advanced Simulation Options

No `[NEEDS CLARIFICATION]` markers were left in spec.md — both source beads (rp-741, rp-2bn) and
this session's own reading of `routes/simulations.py`, `routes/comparisons.py`, `resolution.py`,
`schemas.py`, and both Streamlit pages already resolved the design shape. This phase records the
decisions that turn the spec's requirements into a plan.

## Decision 1: One shared `resolution.py` helper, not duplicated dispatch logic in each route

**Decision**: `generate_configured_return_paths(context, horizon_years, start_plan_year,
generation_mode, historical_block_length, stress_scenario)` lives in `resolution.py` and is called
identically by `resolve_and_run_simulation()` and `resolve_and_compare_simulated()`.

**Rationale**: `rp-9vl`'s own precedent (`build_survival_curves()` /
`validate_survival_curve_coverage()`) is a *shared resolution.py helper*, not each route
independently reimplementing the same logic — this codebase's established pattern is: request-model
**fields** are duplicated per route (no shared Pydantic base exists for `SimulationRequest`/
`ComparisonRequest` today, and this feature does not introduce one), but the **behavior** those
fields drive is centralized in one function both routes call. The dispatch-plus-stress logic here is
meatier than `survival_adjusted`'s own one-line boolean check (a mode branch, a default block length,
a stress-window translation), which makes duplicating it verbatim in both route files a real
maintenance smell `build_survival_curves()`'s own precedent already avoids for a simpler case.

**Alternatives considered**: Duplicating the dispatch logic inline in both
`resolve_and_run_simulation()` and `resolve_and_compare_simulated()`, mirroring exactly how
`generate_return_paths()` is called today (each route already calls it directly, not through a
shared wrapper) — rejected once the added mode-dispatch/stress-overlay logic is factored in; unlike
today's single unconditional call, this would duplicate real branching logic, not just a shared
function call.

## Decision 2: The helper takes primitives, not the request body object

**Decision**: `generate_configured_return_paths()`'s signature takes `generation_mode:
GenerationMode`, `historical_block_length: int`, `stress_scenario: StressScenario | None` (the core
`retirement_planner.simulation` dataclass, not a BFF request model) — not `SimulationRequest |
ComparisonRequest` itself.

**Rationale**: `resolution.py` is consumed by both `routes/simulations.py` and
`routes/comparisons.py`; importing either route's own locally-defined request class into
`resolution.py` would invert this codebase's existing layering (routes import *from*
`resolution.py`, never the reverse — confirmed by reading every existing import in both route
files). Every existing `resolution.py` helper already takes primitives/dataclasses, never a
route-specific request object (`build_survival_curves(household)`, `check_run_cost(context,
candidate_count)`) — this mirrors that convention exactly. Each route is responsible for converting
its own `body.stress_scenario` (a `StressScenarioRequest | None`) into a core `StressScenario`
before calling the shared helper — a two-line, obvious conversion at each call site.

**Alternatives considered**: A `typing.Protocol` describing the three shared fields (this codebase
already uses `Protocol` once, `comparison.models.ReturnSchedule`) — rejected as unneeded ceremony for
three primitives a route can just pass positionally/by keyword; `Protocol` earns its complexity in
`ReturnSchedule`'s case because that interface has actual *behavior* (`return_for_plan_year()`), not
just data.

## Decision 3: `StressScenarioRequest` is one shared nested Pydantic model in `schemas.py`

**Decision**: Unlike `SimulationRequest`/`ComparisonRequest`'s own top-level fields (duplicated per
route, existing convention), the nested stress-scenario shape itself is defined once in
`schemas.py` as `StressScenarioRequest` and imported into both route files — the same way
`schemas.py`'s existing `IncomeStreamRequest` is a shared nested model consumed by
`HouseholdMemberRequest`.

**Rationale**: The three top-level `SimulationRequest`/`ComparisonRequest` classes are independently
maintained by design (this codebase's explicit existing convention, confirmed by reading both files
in full — no shared base exists, and nothing in this feature's scope asks to introduce one). But a
*nested* composite shape shared identically by both is exactly `schemas.py`'s existing job — defining
it twice (once per route file) would be a straightforward, avoidable duplication of a genuinely
identical shape, unlike the top-level classes' own duplication (which reflects that the two
top-level requests are not actually identical — `ComparisonRequest` has `axis`/`candidates`,
`SimulationRequest` has `detail_path_index`).

**Alternatives considered**: Three flat fields (`stress_magnitude`, `stress_duration_years`,
`stress_start_plan_year`) instead of one nested object — rejected; a nested object matches the core
`StressScenario` dataclass's own shape 1:1 (data-model.md), keeps "no stress configured" a single
clean `None` rather than three independently-nullable flat fields that could be partially set, and
mirrors how `RothConversionPlanRequest`/`HsaContributionPlanRequest` already model an opt-in nested
configuration object elsewhere in this same file.

## Decision 4: Default `historical_block_length` — 10 years, applied at the Pydantic field level

**Decision**: `historical_block_length: int = 10` on both request classes (not `None` with a
resolution.py-side default).

**Rationale**: `specs/005-simulation-engine/quickstart.md`'s own worked examples use
`block_length=10` — this is already this codebase's own illustrative reference value for the
parameter, not an invented default. Applying the default at the Pydantic field level (rather than
`None` + an `or 10` fallback inside the shared helper) keeps "what value was actually used" visible
directly on the resolved request body, consistent with how every other optional numeric field in
these two request classes already works (`n_paths`, `seed`, `plan_to_age` — each has its own
resolution-time fallback to the *scenario's* saved value, a different pattern that doesn't apply
here since block length has no scenario-level home to fall back to; a flat literal default is the
simpler, correct choice for a field with no such home).

**Alternatives considered**: Requiring `historical_block_length` whenever `generation_mode ==
"historical_bootstrap"` (no default, reject if missing) — rejected; a household picking bootstrap
mode from the UI shouldn't be forced to also understand and choose a block length before their first
run works, and a request-level required-only-conditionally field is exactly the kind of Pydantic
validator complexity this codebase avoids elsewhere in these two classes (every other optional field
just defaults, with resolution-time fallback where one exists).

## Decision 5: `ValueError` → one shared 422 translator, per-route `try/except`

**Decision**: `generate_configured_return_paths()` lets `generate_historical_bootstrap_paths()`'s and
`apply_stress_scenario()`'s own existing `ValueError`s propagate unchanged; each route wraps its call
in `try/except ValueError` and calls a new shared `invalid_simulation_options_error(exc) ->
HTTPException` (422, `{"error": "invalid_simulation_options", "detail": str(exc)}`).

**Rationale**: Mirrors this codebase's own established two-part pattern for translating a
lower-layer exception into an HTTP response: a plain exception (or, when structured detail is
needed, a small dedicated exception class, e.g. `SurvivalCurveAgeOutOfRangeError`) plus a `_error()`
builder function (`survival_curve_age_out_of_range_error()`, `unsupported_tax_year_error()`) — each
route's own `try/except` block calls the builder, exactly as `resolve_and_run_simulation()` already
does for `BlockingValidationFlagsError`/`UnknownReferenceValueError`/`CostBudgetExceededError`. A
plain `str(exc)` `detail` (rather than a new dedicated exception class carrying structured fields) is
enough here — `generate_historical_bootstrap_paths()`'s and `apply_stress_scenario()`'s own
`ValueError` messages already name the specific problem (block length vs. the documented year count;
the stress window's last plan year vs. the horizon's last plan year) in human-readable form, unlike
`SurvivalCurveAgeOutOfRangeError`'s case, which needed `person_name`/`age` broken out as separate
JSON fields for the UI to act on individually.

**Alternatives considered**: A dedicated `InvalidStressWindowError`/`InvalidBlockLengthError` class
pair, mirroring `SurvivalCurveAgeOutOfRangeError`'s own shape — rejected as unneeded ceremony; the
UI's own error-handling code (per spec.md FR-005/SC-004) only needs to display the message, not act
on individually-typed fields the way `SurvivalCurveAgeOutOfRangeError`'s `person_name`/`age` let the
UI phrase "which household member, which age" — a generic-but-clear message satisfies FR-005 fully.

## Decision 6: `3_Compare.py` gets a new, narrowly-scoped "Advanced overrides" expander

**Decision**: `3_Compare.py` has no "Advanced overrides" expander today (only `2_Run_Simulation.py`
does, for `n_paths`/`seed`/`plan_to_age`/`detail_path_index`). This feature adds a new expander to
`3_Compare.py` containing *only* the three new fields (generation mode, block length, stress
scenario) — not porting `2_Run_Simulation.py`'s existing `n_paths`/`seed`/`plan_to_age` overrides,
which no bead or this spec asks for.

**Rationale**: Matches spec.md's explicit scope boundary and the source feature description's own
instruction ("not porting Compare's missing n_paths/seed/plan_to_age overrides, which is out of
scope"). Gated identically to the existing `survival_adjusted` checkbox
(`if st.session_state.get("compare_engine") != "Deterministic":`) since both are Monte-Carlo-only
(FR-007) — placed in the same conditional block, immediately after that checkbox, so Compare's
Monte-Carlo-only controls read as one coherent section rather than two separately-gated pieces doing
the same check.

**Alternatives considered**: Also porting the missing `n_paths`/`seed`/`plan_to_age` overrides to
Compare while touching this same expander slot — rejected as scope creep genuinely unrelated to
rp-741/rp-2bn; a separate follow-on bead if wanted, not folded into this change.
