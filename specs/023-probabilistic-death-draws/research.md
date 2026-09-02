# Research: Monte Carlo Per-Path Probabilistic Death Draws

## 1. Where the draw-generation logic lives

**Decision**: A new module, `simulation/mortality.py`, holding `generate_death_age_draws()` and a
private `_draw_death_age()` helper -- structurally parallel to `simulation/returns.py`'s
`generate_return_paths()`/`generate_historical_bootstrap_paths()`. `simulation/survival_data.py`
stays pure data (`SURVIVAL_TABLE`, `SurvivalCurve.survival_probability()`), unchanged.

**Rationale**: This project already separates *data* (`historical_data.py`, `survival_data.py`) from
*RNG-driven, seeded generation logic over that data* (`returns.py`). This feature is exactly that
second kind of thing -- a single `random.Random(seed)` stream consumed in a fixed, documented order
to produce one artifact per path, generated once and reused across every comparison candidate,
precisely like `generate_return_paths()`. Putting it in `survival_data.py` instead would blur that
existing boundary for no benefit.

**Alternatives considered**: Adding a method to `SurvivalCurve` itself (`survival_data.py`) --
rejected, since the draw needs `Household`/`HouseholdMember` (for `current_age`, `person_name`) and a
per-path loop over `path_count`, neither of which belongs on a single-curve dataclass whose own
module docstring frames it as pure data for `run_simulation()`'s *existing* metric.

## 2. How a caller opts in

**Decision**: The caller pre-generates the full list of draws via `generate_death_age_draws()`
(exactly as it already pre-generates `return_paths` via `generate_return_paths()`) and passes the
result as a new `run_simulation()`/`compare_*()` parameter, `death_year_draws: list[dict[str, int |
None]] | None = None`. `run_simulation()` itself owns no new RNG state.

**Rationale**: Mirrors `return_paths`' own existing shape exactly, which already satisfies every
constitutional requirement this feature needs (Reproducibility, paired-draw reuse) for free: the same
pre-generated list passed unchanged into every comparison candidate's own `run_simulation()` call
*is* FR-005's path-for-path reuse, with zero new logic in `simulation/compare.py` beyond adding the
one passthrough parameter to each of the four `compare_*()` functions.

**Alternatives considered**: `run_simulation()` accepting a `seed` and drawing internally, once per
call -- rejected: a paired-draw comparison calls `run_simulation()` once per candidate, so an
internally-drawn seed would either redraw per candidate (violating the paired-draw pattern, FR-005)
or require `run_simulation()` to detect "first candidate in this comparison" itself, which it has no
way to know. Pre-generating once, like `return_paths`, sidesteps the problem entirely.

## 3. Coupling to the existing `survival_curves` parameter and `survival_adjusted_success_rate`

**Decision**: `run_simulation()` requires `survival_curves` to be given whenever `death_year_draws`
is given (`ValueError` otherwise). The existing `survival_adjusted_success_rate` computation stays
gated purely on `survival_curves is not None`, exactly as today, unconditional on
`death_year_draws` -- so passing both together computes both: `survival_adjusted_success_rate`'s own
post-hoc threshold check, now applied over `path_results` that already reflect each path's own drawn
death (a real, if unreconciled, combination -- spec.md Edge Cases).

**Rationale**: `survival_curves is not None` already causes `run_simulation()` to append each
covered member's `SurvivalCurve.usage()` (citation/verification `FigureUsage`) to the run's
`figures_used` list -- the exact citation this new capability also needs (FR-009), for free, with no
new figure-attachment code. Requiring `survival_curves` alongside `death_year_draws` reuses that
existing code path instead of duplicating it.

**Alternatives considered**: A fully independent third switch that lets a caller draw per-path deaths
*without* also computing `survival_adjusted_success_rate` -- rejected as unrequested complexity; spec.md's
own Edge Cases explicitly frames the combination as acceptable, not forbidden, and the two metrics
answer different questions (one post-hoc threshold on the *unmodified* path set vs. one that shapes
the path set itself) that a caller may reasonably want side by side.

## 4. Drawing a conditional death age from a `SurvivalCurve`

**Decision**: Standard inverse-transform sampling on the *conditional* survival function, given
already alive at `current_age`. For member with survival curve `S` (keyed by documented integer
ages) and `current_age`:

1. `reference_survival = S(current_age)`, using two documented boundary rules (see below) when
   `current_age` falls outside the curve's documented age range.
2. Draw `V = rng.random()` (uniform on `[0, 1)`).
3. `target = reference_survival * V`.
4. Return the smallest documented age `a >= current_age` with `S(a) <= target`, or `None` if no such
   age exists (every documented age `>= current_age` has `S(a) > target` -- the member's draw places
   them past the curve's own documented range, i.e., they survive the whole modeled horizon).

This is the textbook inverse-CDF draw for "age at death, given alive today": the conditional survival
function is `S(a) / S(current_age)` for `a >= current_age`; setting that equal to `V` and solving for
`a` gives exactly the `target = S(current_age) * V` comparison above. It guarantees the drawn age (when
not `None`) is always `>= current_age` (SC-002) without needing to reject-and-resample.

**Boundary rules for `reference_survival`** (Edge Cases in spec.md):
- `current_age <= 50` (today's `SURVIVAL_TABLE`'s lowest documented age): `reference_survival = 1.0`
  ("certain survival" to the table's own floor -- matches `survival_data.py`'s own module comment
  describing age 50 as "certain survival", even though its illustrative formula computes `S(50) ≈
  0.9948` internally; this feature deliberately reuses that same existing framing rather than
  introducing a second, inconsistent one).
- `current_age > 110` (today's highest documented age): `reference_survival = S(110)` (the oldest
  documented probability). Since the subsequent search only considers documented ages `>=
  current_age`, and none exist above 110, this always resolves to `None` for such a member --
  documented as a known limitation (a `current_age` already past the whole table's range is itself an
  implausible input this engine doesn't otherwise validate; see spec.md Assumptions).
- Otherwise, `current_age` is itself a documented integer age (every whole age 50-110 is documented,
  and `HouseholdMember.current_age: int`), so `reference_survival` is a direct lookup -- never
  interpolated.

**Rationale**: This deliberately diverges from `survival_adjusted_success_rate`'s own existing check
(`survival_curves[...].survival_probability(age) >= 0.5`, entirely unconditional on `current_age`),
per spec.md FR-002. That older check only ever evaluates a probability at one specific future age (a
comparison, not a sample), so its lack of conditioning is a narrow, already-accepted imprecision;
this feature must actually manufacture a self-consistent death *age* that can never fall before
`current_age` (an internally inconsistent, "already dead" path), which unconditional sampling cannot
guarantee. Conditioning costs one extra multiplication and is not meaningfully more complex to
implement or explain than the unconditional alternative.

**Alternatives considered**: Unconditional sampling (draw `a` such that `S(a) <= V` directly, with no
`current_age` reference) -- rejected: for a `current_age` past the curve's midpoint, this frequently
draws an age *below* `current_age`, an already-happened "death," which has no sound way to feed into
`run_plan_projection()` (its `_household_death_tax_year()` helper would compute a death tax year
before `start_tax_year`, effectively "single filing status for the entire horizon" for a member who,
per the scenario's own input, is alive today) and would silently misrepresent what the draw means.
Reject-and-resample until `a >= current_age` -- rejected: correct but strictly more code and one
extra RNG-consumption-count edge case (an unbounded number of `rng` calls per draw) than the
closed-form conditional formula above, which consumes exactly one `rng.random()` call per member per
path, always.

## 5. Deterministic draw order (Constitution Principle II)

**Decision**: `generate_death_age_draws(household, survival_curves, path_count, seed)` builds one
`random.Random(seed)` instance and consumes it path-major: path 0's draws in `household.members`
order (one `rng.random()` call per member), then path 1's, etc. -- exactly mirroring
`generate_return_paths()`'s own documented "path 0's years in order, then path 1's... two `.gauss()`
calls per plan year" convention.

**Rationale**: A second, independent `random.Random` instance (its own `seed` parameter, distinct
from the seed used for `generate_return_paths()`) keeps this feature's reproducibility fully
decoupled from return-path generation -- enabling or disabling this capability, or changing its seed,
never perturbs the market-return sequence a caller already depends on being stable, and vice versa.
`household.members`'s own list order is already a fixed, stable, config-derived order (no dict
iteration order dependency).

**Alternatives considered**: Consuming the *same* `random.Random` stream `generate_return_paths()`
already advances (interleaving death draws with return draws) -- rejected: this would silently change
every existing return-path sequence's output for any caller who turns this feature on (breaking
Principle II's "same seed, same result" guarantee *for return paths specifically*, the one part of
this system every existing test already pins byte-for-byte), and would make the two capabilities'
seeds inseparably coupled, contradicting FR-004's "independently seeded" requirement.

## 6. Threading a path's own draw into `run_plan_projection()`

**Decision**: A new private helper in `monte_carlo.py`, `_household_for_path(household,
death_year_draw)`: when `death_year_draw` is `None` (feature unused, or this path unaffected), return
`household` unchanged (same object, no copy); otherwise return a new `Household` via
`dataclasses.replace()`, with each member's `predicted_death_age` replaced by
`death_year_draw[member.person_name]` (which fully replaces -- never merges with -- the household's
own statically-configured value, per FR-001). Called once per path, immediately before that path's
`run_plan_projection()` call, in both `_run_one_path()` (serial dispatch) and
`_run_one_path_shared()` (parallel dispatch).

**Rationale**: `run_plan_projection()`'s survivor-scenario logic (018) already derives everything --
filing-status switch, survivor Social Security, spending reduction -- purely from
`household.members[*].predicted_death_age` at the top of its own per-year loop; no change to
`comparison/projection.py` is needed at all (FR-006). `household` is already treated as read-only,
shared, unmutated input across every path in today's code (unlike `accounts`/`inherited_accounts`,
which already get a fresh per-path copy) -- substituting a *different* `Household` object for a
single path's call is a strictly additive, backward-compatible change to that existing invariant, not
a violation of it.

**Alternatives considered**: Passing `predicted_death_age` overrides as a new, separate
`run_plan_projection()` parameter instead of building a modified `Household` -- rejected: would touch
`comparison/projection.py`'s already-stable, spec-locked signature (018's own contract) for a change
that a caller-side `Household` copy achieves with zero changes to that module at all, keeping this
feature entirely inside `simulation/`.

## 7. Parallel-dispatch plumbing

**Decision**: `_run_one_path`'s per-call argument tuple and `_run_one_path_shared`'s per-task argument
both gain the path's own `death_year_draw: dict[str, int | None] | None` alongside the existing
`return_path: ReturnPath` (as a `(return_path, death_year_draw)` pair) -- consumed uniformly whether
or not the feature is in use (`run_simulation()` builds a same-length `[None] * len(return_paths)`
list when `death_year_draws` is not given, so both dispatch modes and both feature-on/off states run
through one code path, never two).

**Rationale**: `_init_worker`'s shared, once-per-worker state (household/accounts/strategy/etc.)
stays completely unchanged -- only the *per-task* argument each worker already receives per path
grows by one field, exactly like `_run_one_path`'s existing per-call tuple already carries
`return_path` alongside every shared argument. This keeps the change minimal and keeps FR-007
(byte-identical output when unused) mechanically obvious: `_household_for_path(household, None) is
household`, so nothing downstream can differ.

**Alternatives considered**: Threading the *entire* `death_year_draws` list into `_init_worker`'s
shared state and having each worker index into it -- rejected: `executor.map()` doesn't hand a worker
its own path index, so the worker would need one anyway (via `enumerate`, itself another plumbing
change), for no benefit over pairing the value with its `return_path` up front the same way
`_run_one_path`'s serial-dispatch tuple already does.

## 8. Performance (Constitution Principle VI)

**Decision**: No change to the parallel-dispatch threshold, chunking, or worker-init strategy.
`generate_death_age_draws()` itself is `O(path_count × members)`, each unit of work a handful of
dict lookups and comparisons over a documented range of at most 61 ages -- negligible next to a
single `run_plan_projection()` call. `_household_for_path()` is `O(members)` (2-3 `dataclasses.replace()`
calls) per path. A benchmark case is added to the existing reference-scale performance test
(`tests/integration/test_simulation_performance.py`) with this capability enabled, confirmed well
under the one-minute budget rather than assumed (FR-012, SC-006).

**Rationale**: Directly answers Constitution Principle VI's own instruction to flag and justify (or
verify) a change against the reference-scale budget rather than assume it away.
