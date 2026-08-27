# Feature Specification: Scenario Configuration & Validation

**Feature Branch**: `001-scenario-config-management`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "docs/initial_requirement.md — this initial document can be broken up into multiple features. you are not required to complete all of the requirements in one pass"

**Scope note**: `docs/initial_requirement.md` describes a five-phase retirement planning tool. This spec covers only the input/configuration layer (source doc §3.1, §6, and the "Separation of person data from engine code" and "Versioned scenarios" requirements) — the foundation the tax engine, strategy layer, simulation engine, and reporting features (to be spec'd separately) will all consume. It does not cover running simulations, computing taxes, or producing reports.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Describe a retirement scenario without touching code (Priority: P1)

A user wants to model their retirement plan — household members, account balances, spending needs, Roth conversion plan, state of residence, market assumptions, and simulation settings — by editing a config file, not by editing the simulation program's source code.

**Why this priority**: Every other planned feature (tax engine, strategy comparisons, simulations, reports) depends on scenario data being available as structured, loadable input. Without this, no other feature can be built or demonstrated.

**Independent Test**: Can be fully tested by authoring a config file with a complete household/account/spending/market profile and having the system load it into a structured, in-memory representation — without running a simulation — and confirming every field the user entered is present and correctly typed.

**Acceptance Scenarios**:

1. **Given** a new, empty scenario, **When** a user provides household, account, spending, Roth conversion, state, market, and simulation values in a config file, **Then** the system loads the file into a structured representation with all values accessible by name, with no code changes required.
2. **Given** a config file, **When** a required field (e.g., an account balance) is missing, **Then** the system reports which field is missing instead of loading a partial or default-filled scenario silently.
3. **Given** a loaded scenario, **When** a user changes a single value (e.g., annual spending need) and reloads, **Then** only that value changes in the structured representation — all other fields remain as previously entered.

---

### User Story 2 - Maintain multiple named scenarios for comparison (Priority: P2)

A user wants to keep several named scenarios side by side (e.g., "base case," "early retirement," "high spending") so that later analysis can compare them, instead of only ever having access to the last-edited configuration.

**Why this priority**: Comparative analysis (state comparison, strategy comparison, claiming-age sensitivity — all planned as separate features) requires more than one persisted scenario to exist at the same time. This is the next most foundational capability after single-scenario loading.

**Independent Test**: Can be fully tested by saving two or more distinctly named scenarios, then listing and loading each one independently, and confirming that editing or reloading one named scenario does not alter another.

**Acceptance Scenarios**:

1. **Given** a scenario a user has authored, **When** they save it under a distinct name, **Then** it becomes retrievable by that name independent of any other saved scenario.
2. **Given** two or more saved scenarios, **When** a user requests a list of saved scenarios, **Then** every saved scenario's name is returned, distinguishable from the others.
3. **Given** a saved scenario named "base_case", **When** a user loads it after also having saved and edited a different scenario named "high_spending", **Then** "base_case" reflects only the values it was saved with.

---

### User Story 3 - Catch impossible or out-of-range inputs before they're used (Priority: P3)

A user wants to know immediately, in plain terms, when a scenario they've authored contains a value that cannot be correct (a negative account balance, a Social Security claiming age outside the legal 62–70 range, spending that exceeds total available assets) — before that scenario is used for any downstream calculation.

**Why this priority**: This is a safety net on top of the two capabilities above. It matters, but a user can begin authoring and comparing scenarios (P1/P2) before validation is fully built out; validation prevents wasted downstream effort and misleading results once other features (tax engine, simulation) exist to consume this data.

**Independent Test**: Can be fully tested by authoring configs that each violate exactly one validation rule (negative balance, out-of-range claiming age, spending exceeding assets, etc.) and confirming each is flagged with a message identifying the offending field and the reason, without needing any other feature to be built.

**Acceptance Scenarios**:

1. **Given** a config with a negative account balance, **When** the scenario is loaded, **Then** the system flags that field as invalid and identifies why, rather than accepting the value silently.
2. **Given** a config where a household member's Social Security claiming age is outside 62–70, **When** the scenario is loaded, **Then** the system flags the claiming age as out of the allowed range.
3. **Given** a config where planned annual spending, projected over the plan horizon, exceeds total starting assets with no other income accounted for, **Then** the system flags this as a plausibility concern.
4. **Given** a config with no validation problems, **When** it is loaded, **Then** no validation flags are raised and the scenario is marked usable.

---

### Edge Cases

- What happens when a config file is syntactically malformed (e.g., broken YAML/JSON structure) rather than merely containing bad values? The system must report a load failure distinct from a validation failure, since the file couldn't be parsed into fields at all.
- What happens when a user tries to save a new scenario under a name that already exists? Per FR-015, the previous data under that name is overwritten.
- What happens when a household is defined with only one member (single filer) versus two (MFJ)? The config must support both without requiring different schemas.
- What happens when a claiming age is provided as exactly 62 or exactly 70 (the inclusive boundary values)? These must be accepted, not flagged.
- What happens when spending is entered as zero or a negative number? Zero is a plausible (if unusual) input; negative spending must always be flagged (FR-007).
- What happens when a scenario references a state of residence, market assumption set, or Roth conversion strategy that a future feature (tax engine, strategy layer) doesn't yet support? This layer only needs to store the reference value; validating it against the set of *implemented* tax/strategy modules is the responsibility of those later features, not this one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a user to define a complete scenario — household members (name, current age, Social Security claiming age, Social Security annual benefit), account balances (traditional, Roth, taxable), annual spending need, Roth conversion plan (strategy choice, bracket ceiling or amount, window), state of residence, market return assumptions, and simulation settings (path count, seed, plan-to age) — entirely as data in a config file, without editing the program's source code.
- **FR-002**: The system MUST expose every scenario field to downstream consumers (tax engine, simulation engine, reporting — built as separate features) through one consistent, named structure, so that adding a new field does not require restructuring how existing fields are accessed.
- **FR-003**: The system MUST allow a user to save a scenario under a distinct, user-chosen name and retrieve it later by that name.
- **FR-004**: The system MUST allow a user to list all scenario names currently saved.
- **FR-005**: Saving, editing, or deleting one named scenario MUST NOT alter the stored data of any other named scenario.
- **FR-006**: The system MUST validate a scenario's values when it is loaded, before the scenario is made available for use by any downstream calculation, and MUST report every validation problem found — not only the first one encountered.
- **FR-007**: The system MUST flag a negative value as invalid for any account balance, any household member's Social Security annual benefit, and the annual spending need.
- **FR-008**: The system MUST flag a Social Security claiming age outside the 62–70 (inclusive) range as invalid, for each household member independently.
- **FR-009**: The system MUST flag a scenario where planned annual spending, extended over the configured plan horizon, exceeds total starting assets (with no offsetting income sources configured) as a plausibility concern.
- **FR-010**: The system MUST reject or flag a config missing a value required to run the reference use case's downstream calculations (household, accounts, spending, state, market assumptions, and simulation settings are always required; other fields per Assumptions), and MUST identify which field is missing.
- **FR-011**: Every validation problem reported MUST identify the specific field involved and the reason it was flagged, in terms a non-technical user can act on without reading source code.
- **FR-012**: The system MUST distinguish a config that cannot be parsed at all (malformed file) from a config that parses but contains invalid values, and report each with a message appropriate to that failure type.
- **FR-013**: The system MUST support scenarios with either one household member (single filer) or two (married filing jointly) using the same schema.
- **FR-014**: When the spending-vs-assets plausibility check (FR-009) fails, the system MUST still load the scenario and make it available, but MUST attach a visible warning flag the user can see before relying on results computed from it. This is distinct from "impossible" values (negative balances, out-of-range claiming ages, unparseable files), which always block the scenario from loading.
- **FR-015**: When a user saves a scenario under a name that already exists, the system MUST overwrite the previously saved data under that name — matching a "save over" file-editing model rather than requiring a rename or rejecting the save.
- **FR-016**: "Versioned scenarios" means distinctly-named scenarios coexist and never overwrite each other's data (per FR-005) — it does NOT require the system to retain a history of prior revisions within a single named scenario. A user who wants to preserve an earlier state of "base_case" must save it under a new name before changing it further.

### Key Entities

- **Scenario**: A complete, named set of inputs for one retirement plan run — bundles a Household, a set of Accounts, a Spending profile, a Roth Conversion plan, a state of residence, Market Assumptions, and Simulation Settings. Identified by a user-chosen name.
- **Household**: One or two Household Members plus a filing status (single or married filing jointly).
- **Household Member**: An individual within the household — name, current age, Social Security claiming age, Social Security annual benefit.
- **Account**: A named balance bucket (traditional pre-tax, Roth, taxable) with a current dollar value.
- **Spending Profile**: The household's planned annual spending need in today's dollars.
- **Roth Conversion Plan**: A chosen conversion strategy reference, a bracket ceiling or fixed amount, and a window of years — stored as a reference value for a future strategy-layer feature to interpret; not validated in detail here.
- **Market Assumptions**: Return and allocation figures (equity/bond split, expected return, volatility, correlation) used later by the simulation engine.
- **Simulation Settings**: Path count, random seed, and plan-to age used later by the simulation engine.
- **Validation Flag**: A single reported problem with a Scenario — identifies the field, the reason, and its severity (blocking, for impossible values; warning, for plausibility concerns per FR-014).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from "nothing written down" to a fully loaded, structured scenario in under 5 minutes, without opening or editing any source code file.
- **SC-002**: 100% of scenarios containing a negative balance, an out-of-range claiming age, or a missing required field are caught and reported before being made available to any downstream calculation.
- **SC-003**: A user can maintain at least 10 distinctly named scenarios at once with zero cross-contamination — editing or reloading one never changes the saved data of another.
- **SC-004**: Changing a single input value and producing a newly loadable, comparable scenario requires editing only the config file — zero source code file edits.
- **SC-005**: Given a validation report, a user can identify which field to fix and why without consulting external documentation, for at least 90% of flagged problems.

## Assumptions

- Config files are the unit of scenario authoring (per source doc §5/§6, YAML-style key/value structure), stored under a scenarios location a user can browse directly; the exact file format and directory convention are implementation choices for the planning phase, not user-facing decisions.
- "Required fields" for FR-010 are the fields the reference use case (source doc §2) exercises: household members, accounts, spending, state, market assumptions, and simulation settings. Fields belonging to features not yet built (e.g., a specific Roth conversion strategy identifier) are stored as opaque references here and validated in detail by the feature that implements them.
- This feature does not implement tax logic, RMD logic, Social Security taxability, or Monte Carlo simulation — it only defines, stores, loads, and validates the input data those features will consume. Those are separate, later features per the source document's phased plan.
- "Impossible" values (negative balances, negative Social Security benefits, negative spending, out-of-range claiming ages, unparseable files) always block a scenario from being used downstream; the plausibility-type check (spending vs. assets) instead loads the scenario with a warning flag (see FR-014).
- Single-user, single-household scope only, consistent with the source document's stated non-goals — no multi-household or multi-user concerns apply here.
- No network access is required to author, save, load, or validate a scenario, consistent with the source document's "no runtime network dependency" requirement.
