# Phase 0 Research: Scenario Configuration & Validation

No `[NEEDS CLARIFICATION]` markers remain in the Technical Context — all decisions below were reasonably determined from the source requirement document (`docs/initial_requirement.md`) and the feature spec's Assumptions. This document records the rationale for each so it's auditable rather than implicit.

## 1. Scenario model implementation

**Decision**: Standard-library `dataclasses` for `Scenario` and its nested entities (`Household`, `HouseholdMember`, `Account`, `SpendingProfile`, `RothConversionPlan`, `MarketAssumptions`, `SimulationSettings`), with a separate, explicit `validation.py` module rather than validation embedded in a third-party model library.

**Rationale**: The source document repeatedly frames the current prototypes as already using a `PlanInputs` dataclass and asks for this to become "data (YAML/JSON/CSV)... not hardcoded" — i.e., externalize the *source* of the values, not necessarily replace the modeling approach. Domain-specific validation rules (claiming age 62–70, spending-vs-assets plausibility) don't map cleanly onto a generic schema library's built-in validators and would need custom logic regardless, so a schema library buys little here while adding a dependency and its own error-message format that FR-011 ("plain terms... without reading source code") would still need translating.

**Alternatives considered**:
- *Pydantic*: rejected — adds a runtime dependency for a small, largely flat model; its validation errors are Python-exception-shaped and would need reformatting to satisfy FR-011 and FR-012 (parse failure vs. value failure) anyway.
- *attrs*: rejected — no material benefit over stdlib `dataclasses` for this scope; stdlib keeps the dependency footprint at zero for the model layer itself.

## 2. Config file format

**Decision**: YAML, parsed with `yaml.safe_load` and written with `yaml.safe_dump` (PyYAML).

**Rationale**: The source document's own data model sketch (§6) is written in YAML, and the architecture sketch (§5) names `config/scenarios/*.yaml` explicitly. YAML is more human-editable than JSON for a nested, list-containing structure (household members, market assumptions) and supports comments, which matters since this is a hand-edited file, not a machine-to-machine payload. `safe_load` is used specifically to avoid executing arbitrary Python tags from a file a user might casually copy/paste from elsewhere.

**Alternatives considered**:
- *JSON*: rejected — no comments, stricter trailing-comma/quoting rules make hand-editing more error-prone, and the source document doesn't use it anywhere in its own examples.
- *TOML*: rejected — awkward for the nested list-of-household-members shape; no precedent in the source document.

## 3. Scenario storage layout

**Decision**: One YAML file per named scenario, at `config/scenarios/<name>.yaml`, where `<name>` is the user-chosen scenario name (sanitized to a filesystem-safe form).

**Rationale**: Directly satisfies FR-003–FR-005: each scenario is independently retrievable by name, and saving/editing one cannot corrupt another because they're physically separate files. It matches the architecture sketch's `config/scenarios/*.yaml` layout, and it's inherently git-diffable — a user can track scenario history externally via version control even though this feature itself doesn't implement revision history (per FR-016).

**Alternatives considered**:
- *Single YAML file holding all scenarios as a dict*: rejected — a write while saving one scenario touches the whole file, so a crash or bug mid-write risks corrupting every other scenario, which would violate FR-005's isolation guarantee.
- *SQLite or another embedded database*: rejected — overkill for single-user, low-tens-of-scenarios scale (Scale/Scope), not human-editable/diffable, and adds a dependency the source document's "no runtime network dependency, offline" NFR doesn't require paying for.

## 4. Testing framework

**Decision**: pytest.

**Rationale**: De facto standard for Python projects; the source document's own Validation Plan (§7) is phrased as a list of unit tests ("Unit tests for RMD divisor table against IRS Pub. 590-B values", "Each state tax module tested against at least one hand-calculated example") — a style pytest's parametrization supports well and later features (state-by-state tax modules) will lean on heavily.

**Alternatives considered**:
- *`unittest` (stdlib)*: rejected — more boilerplate per test, weaker parametrization ergonomics for the "same check across many states/scenarios" pattern this project will need repeatedly in later phases.

## 5. Validation result shape

**Decision**: `validate(scenario) -> list[ValidationFlag]`, where `ValidationFlag` carries `field`, `message`, and `severity` (`"blocking"` or `"warning"`), and validation always runs to completion and collects every problem rather than raising/stopping at the first one.

**Rationale**: FR-006 explicitly requires reporting every validation problem found, not only the first. FR-014 requires two severities to coexist (impossible values block; the spending-vs-assets plausibility check warns but still loads), so severity must be a first-class field on each flag rather than an implicit "any flag = reject" convention.

**Alternatives considered**:
- *Raise an exception on first invalid field*: rejected — fails FR-006 (report every problem) and would force a user through a fix-one/reload/fix-next loop that SC-005 (identify and fix without external docs, evaluated per flagged problem) doesn't require if all flags are shown at once.

## 6. Package layout / name

**Decision**: `src/retirement_planner/scenario/` as a self-contained subpackage.

**Rationale**: No package name is established anywhere in the repository yet (no existing `pyproject.toml`, no prototype scripts present in this repo despite being referenced by the source document). `src/`-layout is standard Python packaging practice that avoids accidentally importing an uninstalled package from the working directory. Scoping this feature's code to a `scenario` subpackage keeps it independently importable by later features (tax engine, simulation engine, reporting) without those features needing to exist yet.

**Alternatives considered**:
- *Flat top-level module (`scenario.py` at repo root)*: rejected — doesn't scale to the multi-module architecture the source document's §5 sketch already anticipates (`engine/`, `reporting/`, etc., each as their own package).
