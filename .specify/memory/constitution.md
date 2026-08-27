<!--
Sync Impact Report
Version change: [TEMPLATE — unratified] → 1.0.0
Rationale: Initial ratification. No prior constitution existed (only the unfilled placeholder
template was present in git history), so this is treated as a first adoption, not an amendment.

Modified principles: n/a (initial ratification)

Added sections:
  - Core Principles I–VI (Accuracy Over Cleverness, Reproducibility, Auditability,
    Extensibility Through Module Interfaces, Offline-First / No Runtime Network Dependency,
    Performance Budget)
  - Technology & Architecture Constraints
  - Development Workflow & Quality Gates
  - Governance

Removed sections: n/a

Templates requiring follow-up:
  - .specify/templates/plan-template.md — Constitution Check gate: ✅ already present as a
    generic gate section; no structural change needed, but /speckit-plan runs on features
    created before this ratification (e.g., 001-scenario-config-management) should be
    re-checked against these principles the next time that feature's plan.md is touched.
  - .specify/templates/spec-template.md — ✅ no constitution-specific content, no change needed.
  - .specify/templates/tasks-template.md — ✅ no constitution-specific content, no change needed.

Deferred items / TODOs: none — all placeholders below are filled with concrete values derived
from docs/initial_requirement.md §4 (Non-Functional Requirements), §5 (Architecture Sketch), and
§7 (Validation Plan).
-->

# Retirement Planning Tool Constitution

## Core Principles

### I. Accuracy Over Cleverness

Where a simplification is made — a blended state tax rate, fixed real-terms tax brackets, an
omitted IRMAA or NIIT calculation, or any other approximation — it MUST be explicitly documented
both in code (comments at the point of simplification) and in user-facing output. A simplified or
unverified figure MUST NOT be presented as settled or authoritative.

**Rationale**: This tool informs real, irreversible retirement decisions (state of residence,
Roth conversion amounts, claiming ages). A simplification silently absorbed into a "success rate"
number is worse than no number at all, because it looks precise while hiding its own error bars.

### II. Reproducibility

Given the same scenario configuration and the same random seed, the system MUST produce identical
results on every run. Any change — refactor, dependency upgrade, or new feature — that breaks
reproducibility of a fixed seed's output MUST be treated as a breaking change and called out
explicitly, not merged silently.

**Rationale**: Scenarios are revisited and re-run over months or years as inputs change. Without
reproducibility, a user cannot tell whether a changed result reflects a changed assumption or a
silent bug in the engine.

### III. Auditability

Every tax rate, exclusion amount, bracket threshold, or other externally-sourced figure MUST carry
a citation and a last-verified date in the code that defines it. Any figure not yet confirmed
against a primary source MUST propagate a visible "needs verification" flag into report/chart
output — it MUST NOT be indistinguishable from a verified figure in what the user sees.

**Rationale**: Tax law changes yearly and several figures used by this tool (e.g., state exclusion
amounts, legislative sunset schedules) are explicitly open items. A user comparing states or
strategies needs to know which numbers are load-bearing fact and which are still provisional.

### IV. Extensibility Through Module Interfaces

Adding a new state tax module, a new withdrawal-sequencing strategy, or a new Roth conversion
strategy MUST NOT require modifying the simulation core. Each such extension point MUST be
implemented against a documented, stable interface (e.g., a `compute_state_tax(...)`-shaped
function, a withdrawal-strategy interface) that new implementations plug into without the core
engine knowing which concrete implementation it's running.

**Rationale**: The tool's value grows by adding states and strategies over time (currently 9
candidate states, more strategies planned). If each addition touches the simulation core, the
core accumulates risk and regression surface with every extension instead of staying stable.

### V. Offline-First, No Runtime Network Dependency

Scenario loading, validation, tax calculation, simulation, and reporting MUST run entirely offline
once a scenario is configured. Any rate lookup, data refresh, or source-verification step against
an external system MUST be a separate, explicit, user-invoked action — never something a
simulation run depends on to complete.

**Rationale**: This is a single-user planning tool meant to be rerun repeatedly, including in
contexts with no reliable network access. A hidden network dependency would make runs
non-reproducible (Principle II) and fragile in ways unrelated to the financial model itself.

### VI. Performance Budget

The reference-scale simulation (currently 3,000–5,000 Monte Carlo paths × 9 candidate states)
MUST complete in well under a minute on a standard laptop. Any new feature — historical bootstrap
return sampling, joint-life RMD tables, mortality-adjusted survival curves, or similar — that would
regress this budget MUST be flagged and justified (or optimized) before being merged, not
discovered as a surprise afterward.

**Rationale**: Interactive iteration is the whole point of this tool — a user adjusting one input
and re-running expects a laptop-scale wait, not a batch job. Losing that responsiveness as
features accumulate would undermine the "rerun as things change" purpose stated in the tool's
own charter.

## Technology & Architecture Constraints

- **Language**: Python 3.11+ for all engine, tax-module, and reporting code, consistent with the
  existing prototypes this tool extends.
- **Config as data, not code**: All person, account, and assumption inputs MUST live in structured
  config files (YAML), never hardcoded into engine or simulation source. Changing a number MUST
  NOT require a code change or a code review of engine logic.
- **Paired-draw comparison is the standard pattern**: Any comparative run — across states,
  withdrawal strategies, Roth conversion strategies, or Social Security claiming ages — MUST reuse
  the paired-draw Monte Carlo methodology (identical random draws reused across every compared
  scenario) rather than each comparison feature reimplementing its own ad hoc comparison logic.
- **Scope boundary with the working document**: The tool computes financial/tax outcomes only.
  Qualitative, non-financial factors (insurance cost reality, healthcare access rankings, and
  similar) remain in the separate narrative working document and MUST NOT be modeled or scored
  inside the simulation engine — only accepted as manual config inputs where a dollar figure is
  needed (e.g., an actual insurance quote).

## Development Workflow & Quality Gates

- **Regression baseline**: Any refactor of the engine MUST reproduce the same directional
  conclusions the existing prototype outputs already produced for the reference use case before
  the refactor is considered complete.
- **Verified-figure gate**: A state tax module, or any other externally-sourced tax rule, MUST NOT
  be marked "verified" in output until cross-checked against a primary source, per Principle III.
- **Unit test coverage for numeric primitives**: RMD divisor tables, federal bracket math, and each
  state's tax module MUST have unit tests against published or hand-calculated reference values
  before being used in any comparative run.

## Governance

This constitution supersedes ad hoc practice for this project. Every `/speckit-plan` run MUST
include a Constitution Check evaluated before Phase 0 research and re-checked after Phase 1
design; a plan with an unresolved violation MUST NOT proceed to `/speckit-tasks`. A violation
surfaced during `/speckit-analyze` is always CRITICAL and MUST be resolved by adjusting the spec,
plan, or tasks — never by reinterpreting or silently dropping the principle.

**Amendments**: Changes to this document are made via `/speckit-constitution` only, and MUST
include an updated Sync Impact Report describing what changed and why.

**Versioning policy** (semantic versioning):
- **MAJOR**: A principle is removed, or redefined in a backward-incompatible way.
- **MINOR**: A new principle or section is added, or existing guidance is materially expanded.
- **PATCH**: Wording, typo, or clarification fixes with no semantic change.

**Compliance review**: Any feature spec, plan, or task list already in progress at the time this
constitution is ratified or amended SHOULD be re-checked against it the next time that feature is
touched, rather than retroactively re-run in full.

**Version**: 1.0.0 | **Ratified**: 2026-08-27 | **Last Amended**: 2026-08-27
