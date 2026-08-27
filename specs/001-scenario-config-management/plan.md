# Implementation Plan: Scenario Configuration & Validation

**Branch**: `001-scenario-config-management` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-scenario-config-management/spec.md`

## Summary

Provide a data-only, code-free way to author a complete retirement scenario (household, accounts, spending, Roth conversion plan, state, market assumptions, simulation settings) as a human-editable YAML file; save/list/load it under a distinct, user-chosen name with filesystem-level isolation between scenarios; and validate it on load — blocking on impossible values (negative balances, out-of-range claiming ages, unparseable files) and warning (but still loading) on the spending-vs-assets plausibility check. This is a pure library layer: it defines the `Scenario` data model and the load/save/list/validate operations that the tax engine, strategy layer, simulation engine, and reporting features (spec'd separately) will all import and build on. No CLI, tax logic, or simulation logic is implemented here.

## Technical Context

**Language/Version**: Python 3.11+ (the source requirement document frames this feature as extending existing `PlanInputs`-dataclass-based prototypes and a "Python-first workflow"; no other language is implied anywhere in the source material)

**Primary Dependencies**: Standard library `dataclasses` for the scenario model; PyYAML (`yaml.safe_load` / `yaml.safe_dump`) for config file parsing and writing. No web framework, database driver, or numeric libraries are needed for this feature — those arrive with later features (simulation engine, tax engine).

**Storage**: Local filesystem — one YAML file per named scenario under `config/scenarios/<name>.yaml`. No database.

**Testing**: pytest

**Target Platform**: Local developer/user machine (Linux/macOS/Windows), invoked as a library from a future CLI or notebook — offline, no network access required at runtime.

**Project Type**: Single Python library project (src/ layout) — no frontend/backend split, no mobile component.

**Performance Goals**: Loading, saving, listing, or validating a single scenario should complete in well under 1 second on a laptop — this is interactive, file-sized I/O, not simulation-scale computation (that budget belongs to the simulation engine feature).

**Constraints**: Must run fully offline (no network calls to load/save/validate); scenario files must remain human-readable/editable and diffable in version control (rules out binary or database storage); saving/editing one named scenario must never mutate another (FR-005).

**Scale/Scope**: Single user, single household; expect low tens of named scenarios coexisting (SC-003 requires at least 10) — not a multi-tenant or high-volume concern.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still the unfilled template (`[PROJECT_NAME] Constitution` with all placeholder tokens) — no principles have been ratified for this project yet. There are no gates to evaluate against. This plan proceeds without constitutional constraints; if a constitution is ratified later, this feature should be checked against it retroactively.

**Post-Phase 1 re-check**: No change — the constitution is still unratified after design (research.md, data-model.md, contracts/, quickstart.md). No gates were introduced or violated by the design artifacts.

## Project Structure

### Documentation (this feature)

```text
specs/001-scenario-config-management/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── scenario-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
config/
└── scenarios/                    # user-authored + saved named scenario files (data only, not code)
    └── .gitkeep

src/
└── retirement_planner/
    ├── __init__.py
    └── scenario/
        ├── __init__.py
        ├── models.py             # Household, HouseholdMember, Account, SpendingProfile,
        │                         # RothConversionPlan, MarketAssumptions, SimulationSettings,
        │                         # Scenario, ValidationFlag dataclasses
        ├── loader.py              # parse a YAML file into a Scenario; malformed-file errors (FR-012)
        ├── store.py                # save_scenario, list_scenarios, load_scenario over config/scenarios/
        └── validation.py           # validate(scenario) -> list[ValidationFlag]; FR-007..FR-011, FR-014

tests/
├── conftest.py                        # redirects scenario storage to a tmp_path fixture for every test
├── unit/
│   └── scenario/
│       ├── test_models.py
│       ├── test_loader.py
│       ├── test_validation.py
│       └── test_store.py
└── integration/
    ├── test_scenario_lifecycle.py   # author -> save -> list -> load -> validate; multi-scenario
    │                                  # isolation (SC-003); overwrite-on-save (FR-015)
    └── test_performance.py           # save/list/load/validate complete well under 1s (Performance Goals)
```

**Structure Decision**: Single Python library project using a `src/` layout (Option 1 from the template, specialized). `config/scenarios/` holds only user data (YAML), never code, matching the source document's architecture sketch (§5) where `config/` is explicitly data and `engine/`/`reporting/` (future features) are code. This feature's code lives in `src/retirement_planner/scenario/` as a self-contained subpackage so later features (tax engine, simulation engine) can `import retirement_planner.scenario` without depending on anything not yet built.

## Complexity Tracking

*No constitution gates are defined (see Constitution Check above), so no violations require justification.*
