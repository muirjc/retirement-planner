# Remaining Scope: `docs/initial_requirement.md` vs. Specs 001–005

**Purpose**: A section-by-section reconciliation of the original requirements document against the five specs delivered so far (`001-scenario-config-management` through `005-simulation-engine`), so a follow-on `/speckit-specify` run has a precise, sourced starting point instead of re-deriving coverage from scratch.

**Method**: Every functional requirement table, phase, and open question in `docs/initial_requirement.md` was checked against each spec's own Scope Note, Functional Requirements, and Assumptions sections (specs themselves are the source of truth for what they deliver — not the source code). Nothing below contradicts what `001`–`005` already say about their own boundaries; this document just collects those boundaries into one place and asks "does anything on the source document's list currently belong to *no* spec at all?"

**Bottom line**: One requirements area — **§3.6 Reporting/Output** — has no spec at all, in draft or otherwise. Two further functional areas — **IRMAA/NIIT** (§3.2) and **HSA coordination** (§3.3) — were consciously and explicitly deferred by name in `002`'s and `003`'s own Assumptions, but likewise have no spec yet. Everything else in §3 is covered by an existing spec, in most cases with an explicitly documented, narrower first slice and named follow-on work. Section-by-section detail and a residual implementation backlog follow.

---

## 1. Coverage by source-document section

| Source doc section | Covered by | Status |
|---|---|---|
| §1 Purpose (longevity, tax optimization, location comparison) | `001`–`005` jointly | ✅ All three questions have an engine now: longevity/success-rate (`005`), tax optimization via strategy comparison (`004`, `005`), location comparison via the new state axis (`005`). Presenting the answer to a user is §3.6's job — see below. |
| §1.1 Non-goals | N/A (boundary-setting, not a requirement) | ✅ Respected throughout — no spec models investment advice, real-time aggregation, or estate planning. |
| §2 Reference Use Case | `001`–`005` (mechanics); not yet exercised end-to-end | ⚠️ See §3 below — the mechanics all exist, but the actual 9-state, MFJ, Roth-bridge reference scenario has never been run as one worked example, and only 3 of 9 candidate states have real tax modules. |
| §3.1 Input / Configuration Layer | `001-scenario-config-management` | ✅ Complete for its stated scope. |
| §3.2 Tax Engine | `002-tax-calculation-engine` | ✅ Complete for its stated scope — **explicitly excludes IRMAA and NIIT** (`002` Assumptions: "out of scope for this feature... will be specified as a separate feature"). |
| §3.3 Retirement Account Mechanics | `003-retirement-account-mechanics` | ✅ Complete for its stated scope — **explicitly excludes HSA contribution/eligibility timing** (`003` Assumptions: "out of scope for this feature... will be specified as a separate, later feature"). |
| §3.4 Strategy / Optimization Layer | `004-strategy-comparison-layer` | ✅ Complete (deterministic layer); Monte Carlo version of the same comparisons delivered by `005`. |
| §3.5 Simulation Engine | `005-simulation-engine` | ✅ Complete for its stated scope. |
| §3.6 Reporting / Output | **No spec** | ❌ **Gap.** Every one of `002`, `004`, and `005`'s scope notes explicitly names §3.6 (fan chart, overlay chart, summary table, CSV export, verification-flag rendering) as "a separate future feature" — but that feature has never been created. See §2 below. |
| §4 Non-Functional Requirements | `001`–`005` via the project constitution | ✅ Accuracy-over-cleverness, reproducibility, auditability, extensibility, offline-first, and the performance budget are all evaluated per-feature in each spec's Constitution Check. |
| §5 Architecture Sketch | `001`–`005` (`config/`, `engine/`≈`scenario`+`tax`+`mechanics`+`comparison`+`simulation`) | ⚠️ Mostly realized, with one component never addressed: **`cli.py` / notebook interface** — the sketch's own "entry point" line. All five specs are explicitly library-only ("no CLI," per `004`'s and `005`'s plan.md Summary sections). Nothing currently lets a person actually run the tool. See §2 below. |
| §6 Data Model (Sketch) | `001` (`Scenario`, `Household`, `MarketAssumptions`, `SimulationSettings`, etc.) | ✅ Realized, field-for-field, in `001`'s `data-model.md`. |
| §7 Validation Plan | Partially executed | ⚠️ See §3 below — several checkboxes remain formally unchecked. |
| §8 Phased Delivery | Phase 1 ✅, Phase 2 ✅ (`001`,`002`), Phase 3 ✅ (`004`), Phase 4 ⚠️ partial (`005` did historical bootstrap + mortality; **IRMAA/NIIT not done**), Phase 5 ❌ (HSA not done; verification-flag propagation into reports not done, since reports don't exist yet) | ⚠️ See §2. |
| §9 Integration Boundary with the Working Document | `001`'s general-purpose scenario schema | ✅ No special-purpose field is needed — any manual dollar figure (e.g., an insurance quote) is already just a normal scenario input. Not a gap. |
| §10 Open Questions | Partially resolved | ⚠️ See §3 below. |

---

## 2. The gap: §3.6 Reporting / Output (no spec exists)

This is the one requirements area from the source document with **zero** spec coverage — not even a narrowed first slice. Every upstream feature was written to hand off exactly the data this feature would need:

- `002-tax-calculation-engine` and `003-retirement-account-mechanics` attach a `FigureUsage` list (citation, last-verified date, verified flag) to every result — the "needs verification" flag data §3.6 asks to surface is already produced and threaded through `004` and `005` untouched, waiting for something to render it.
- `004-strategy-comparison-layer` produces a `ComparisonResult` (one outcome per candidate strategy/order/claiming-age pair) — the structured input an "overlay chart... generalized to any comparison axis" needs.
- `005-simulation-engine` produces a `SimulationRun`/`SimulationComparisonResult` with `success_rate`, `percentile_bands` (per-plan-year percentile ending balances — literally fan-chart data), and per-path `cumulative_tax_paid` — the structured input the fan chart, the summary statistics table, and the source document's explicit ask for "median lifetime taxes paid per scenario" all need. **No feature currently computes that median** — `SimulationRun.path_results` has the per-path figure, but no aggregate.

None of that is presentation. What's missing, itemized against the source document's own §3.6 table:

| Requirement (source doc §3.6) | Data available from | Rendering/aggregation still needed |
|---|---|---|
| Fan chart (percentile bands over time) | `005`'s `SimulationRun.percentile_bands` | Chart rendering itself |
| Multi-scenario overlay chart, generalized to any comparison axis | `004`'s `ComparisonResult` / `005`'s `SimulationComparisonResult` | Chart rendering itself |
| Summary statistics table (success rate, median/percentile ending balance, depletion age; **+ median lifetime taxes paid**) | `005`'s `SimulationRun` (success rate, percentile bands, per-path depletion year, per-path cumulative tax) | The median-lifetime-tax aggregate is not yet computed anywhere; table assembly/formatting is not yet built |
| CSV/data export (feeding the markdown working-document pipe-table workflow, per §9) | All of `001`–`005`'s structured results | Export itself |
| Verification flags surfaced in output (the "red-bar convention") | `FigureUsage` lists, threaded through every feature's `figures_used` field | Visual/tabular surfacing itself |

**Also unaddressed, and adjacent to this gap**: the source document's Architecture Sketch (§5) names a `cli.py / notebook interface` as the tool's entry point. No spec has built one — `001`–`005` are all explicitly library-only. Without either a CLI/notebook layer or a reporting layer, there is currently no way for a person to actually run this tool end-to-end and see an answer to the three questions in §1. Whether the entry point is folded into the reporting feature or spec'd as its own follow-on is an open design choice for whoever writes that spec next.

**Recommendation**: Spec this as feature `006`, likely titled around "Reporting & Output" or "Results Presentation," covering §3.6 plus (at minimum) a decision on where the CLI/notebook entry point lives. Every dependency it needs already exists and is stable.

---

## 3. Deferred-but-unspecified functional areas

These were not overlooked — each is called out by name in an existing spec's Assumptions as consciously out of scope, with a stated reason and a stated intent to spec it later. That "later" hasn't happened yet.

### 3.1 IRMAA and NIIT modeling (source doc §3.2, Phase 4)

`002-tax-calculation-engine`'s Assumptions: *"IRMAA and NIIT are out of scope for this feature... They will be specified as a separate feature."* `005-simulation-engine` reconfirms the deferral is still in effect. No spec exists. This affects any household whose MAGI could cross a Medicare premium surcharge tier or the NIIT threshold — directly named in the source document as relevant "given the existing Medicare/HSA coordination work in the state comparison doc."

### 3.2 HSA contribution/eligibility timing (source doc §3.3, Phase 5)

`003-retirement-account-mechanics`'s Assumptions: *"HSA contribution/eligibility timing... is out of scope for this feature... It will be specified as a separate, later feature."* No spec exists. The source document specifically motivates this with "the documented 6-month Medicare backdating contribution trap and the younger-spouse-retains-eligibility finding" — i.e., this is not a nice-to-have, it's flagged as a real trap the current tool cannot yet catch.

**Recommendation**: Both are legitimate follow-on specs (features `007`/`008`, or combined into one "Advanced Tax & Benefits Modeling" feature if IRMAA/NIIT/HSA are judged small enough individually). Neither blocks `006` (Reporting) — they extend the tax/mechanics engines those reports will draw from, so sequencing them before or after `006` is a scheduling choice, not a dependency requirement.

---

## 4. Residual implementation backlog (no new spec needed — follow-on work already named inside existing specs)

These are gaps *within* already-spec'd features, each already flagged in that feature's own spec/plan as explicit follow-on work — listed here only so they aren't lost, not because they need a new `/speckit-specify` pass.

1. **Only 3 of the 9 candidate states have real tax modules.** `002`'s own FR-017/Assumptions: it delivers SC, DE, and FL "to exercise the zero-tax behavior"; GA, NC, TN, MS, PA, NH are named explicitly as "follow-on work against that same interface." The source document's Reference Use Case (§2) treats all 9 as the acceptance-test baseline — that baseline can't be fully exercised until the remaining six modules exist.
2. **The Joint Life RMD Table is implemented but never actually invoked.** `003` built genuine Uniform Lifetime *and* Joint Life table logic behind a `spouse_is_sole_beneficiary` parameter — but `004`'s and `005`'s multi-year projection loops always pass `spouse_is_sole_beneficiary=False`, because `001`'s `Household`/`HouseholdMember` schema has no field recording actual beneficiary designation. `004`'s research.md calls this out directly: *"extending `001`'s schema with a sole-beneficiary field is a natural follow-on, out of this feature's scope."* Nothing has picked that up yet — it would be a small, additive `001` schema amendment plus a one-line change in `004`'s and `005`'s projection loops.
3. **`005`'s historical-return series and survival-curve table are synthetic placeholders, not real data.** Both are clearly labeled and `verified=False` (per Constitution Principle III), generated deterministically for structural completeness because this project has no runtime network access. The source document's own Open Questions (§10) never resolved "which return series and what date range" — that's still open. Sourcing a real series (and a real actuarial table) is a data task, not a design task, but it's a prerequisite for either table to ever be marked verified.
4. ~~**The reference use case has never actually been run.**~~ **Resolved** — `examples/reference_scenario.py` now drives the full `001 → 002 → 003 → 004/005` pipeline against the §2/§6 reference profile and prints answers to all three §1 questions. It still can't exercise the full 9-state comparison (item 1 above still blocks that — it currently runs SC/DE/FL only, and only over a single tax year because DE's bracket table doesn't yet cover the full horizon), and `config/scenarios/` is still empty (this example builds its scenario in Python, not from a saved YAML file) — but the pipeline itself has now actually been exercised end-to-end at least once.
5. **Several Validation Plan (§7) checkboxes remain formally unchecked**: RMD divisor values against IRS Pub. 590-B, federal bracket math against published 2026 MFJ thresholds, each state module against a hand-calculated example, and the GA HB 463 / SC phase-in / DE exclusion figure cross-checks. All of `002` and `003`'s numeric primitives already have unit tests against *internally* constructed reference cases (per each feature's Development Workflow gate) — what's outstanding is cross-checking those illustrative figures against actual primary sources, which every affected module already flags via `verified=False`.
6. **The source document's "reproduce prototype output exactly" regression check (§7) was never literally executed.** `004`'s and `005`'s plan.md both address this directly and explain why a bit-for-bit diff against the prototype's saved CSVs isn't meaningful (different RNG algorithm, and `004`'s deterministic engine has no prototype equivalent to diff against) — but the directional-conclusion comparison the source document actually cares about (does the refactored engine agree with the prototype about *which* state/strategy wins) has also never been run as an explicit check.

---

## 5. Suggested next steps

1. **`/speckit-specify` feature `006`** covering §3.6 Reporting/Output (fan chart, overlay chart, summary table with the median-lifetime-tax addition, CSV export, verification-flag surfacing) — the only fully unspec'd requirements area, and the one that turns `001`–`005`'s engines into something a person can actually read an answer from. Decide there whether the CLI/notebook entry point (§5) is in-scope or its own follow-on.
2. **`/speckit-specify` feature(s) for IRMAA/NIIT and HSA** — each already has a clear, named scope boundary waiting in `002`'s and `003`'s Assumptions; no rediscovery needed.
3. Track items 1–6 in §4 above as implementation backlog (beads issues, per this project's tracking convention) rather than new specs — each already has its resolution described in an existing feature's own docs.
