# Phase 0 Research: Federal & State Tax Calculation Engine

No `[NEEDS CLARIFICATION]` markers remain in the Technical Context. Both of spec.md's clarifications (out-of-schedule tax year behavior, required state module coverage) were already resolved with the user during `/speckit-specify`; this document covers the implementation-level decisions needed to move from spec to design.

## 1. No new runtime dependencies

**Decision**: Standard library only — no PyYAML, no numeric library, nothing new added to `pyproject.toml`.

**Rationale**: Unlike `001` (which parses user-authored YAML files), this feature's inputs arrive as already-typed Python values from a caller, and its rule tables are Python module constants, not files to parse. Federal/state tax computation is bracket comparisons and multiplication — the standard library is sufficient.

**Alternatives considered**: None seriously — there's no gap a library would fill here.

## 2. Tax rule tables as Python modules, not YAML

**Decision**: Federal brackets, Social Security thresholds, and each state's brackets/exclusions are Python module-level constants (dataclass instances), not YAML config files — despite `001` establishing YAML as this project's convention for scenario data.

**Rationale**: See plan.md's Constitution Check for the full reasoning. Short version: `001`'s "config as data" rule targets *user-editable scenario inputs* (accounts, spending, claiming ages) — figures a user changes from run to run without needing a code review. Tax law figures are the opposite: Principle III (Auditability) requires every one to carry a citation and last-verified date and to be reviewed like code when it changes. A YAML file inviting silent, unreviewed edits to a tax bracket would undermine that discipline. The source document's own architecture sketch (§5) already treats these as `.py` files (`config/federal_tax_rules.py`, `config/state_tax_rules/*.py`), reinforcing this reading — the sketch's use of `config/` there is about *logical grouping* ("configuration of the tax system"), not literally "the YAML-config layer" `001` built.

**Alternatives considered**:
- *YAML files under `config/`, parsed like scenarios*: rejected — invites unreviewed, uncited edits to legally-sourced figures; also each state's bracket-by-bracket math (not just its numbers) needs to run as code regardless, so splitting "the numbers" into YAML while "the math" stays in Python buys little and adds a parsing step with no offsetting benefit.
- *A single shared dict of blended rates (the prototype's current approach)*: rejected — this is exactly what FR-005/FR-006 require replacing.

## 3. Every figure is a year→value schedule, even single-year figures

**Decision**: One `SourcedFigure` type models every rate/bracket edge/exclusion amount as `{schedule: dict[int, float], citation: str, last_verified: date, verified: bool}` — even a figure that (for now) only has one documented year gets a one-entry schedule, rather than maintaining two separate types (a plain single-value figure and a separately-typed scheduled figure).

**Rationale**: FR-012 requires schedule support for figures that change by law (GA/NC/MS-style sunset changes); FR-016 requires refusing a computation for a year outside a figure's schedule. A single uniform type means every figure — whether it happens to have one documented year or five — goes through the same lookup-and-refuse-if-missing code path (US3), with no special-casing between "figures that can have a schedule" and "figures that can't."

**Alternatives considered**:
- *Two types (`Figure` with a plain value, `ScheduledFigure` with a schedule)*: rejected — every consumer of a figure would need to handle both shapes, and a figure that's single-valued today might legitimately need a second scheduled value added later (exactly what happened to GA/NC/MS); a uniform type means that's just adding a schedule entry, not a type migration.

## 4. Out-of-schedule year: a dedicated exception, not a sentinel return value

**Decision**: Looking up a figure for a tax year outside its schedule raises `UnsupportedTaxYearError(figure_name, requested_year, available_years)` — it does not return `None`, `NaN`, or a zero.

**Rationale**: Matches the pattern `001` already established with `ScenarioParseError` for "this input cannot produce a result at all" versus a value-level flag for "this produced a result, but here's a concern about it" (`ValidationFlag`). An out-of-schedule year is the former — there is no reasonable tax figure to return, so returning any numeric sentinel risks silently propagating a wrong number into a caller's arithmetic, which is exactly what FR-016 (refuse and report) is designed to prevent.

**Alternatives considered**:
- *Return `None` / `0.0` and let the caller check*: rejected — too easy for a caller to forget the check and silently treat "unsupported" as "zero," which is a materially different (and wrong) tax outcome.

## 5. State module interface: a plain function + a registry dict

**Decision**: Each state module exposes one function, `compute_tax(income, ages, filing_status, tax_year) -> StateTaxResult`, matching the shape (not the literal name) of the source document's `compute_state_tax(income_components, filer_ages, params) -> float` sketch. A single `STATE_MODULES: dict[str, Callable]` registry in `tax/state/__init__.py` maps a state code to its module's `compute_tax` function; the top-level dispatcher looks up the function by state code rather than branching on state in a big if/elif chain.

**Rationale**: Directly satisfies FR-005 (independent modules) and SC-006 (adding a state touches no other file except adding one new module and one new registry entry). A plain function is the simplest thing that satisfies "every state module has the same shape" — no class hierarchy or abstract base class is needed since there's no shared state or lifecycle across calls, just a pure function per state.

**Alternatives considered**:
- *Abstract base class / `Protocol` with a `StateTaxModule` interface*: rejected as unnecessary ceremony — a `Callable[[IncomeComponents, FilerAges, FilingStatus, int], StateTaxResult]` type alias documents the same shape without requiring every state module to define a class.
- *A big `if state == "SC": ... elif state == "DE": ...` dispatcher*: rejected — this is precisely the "adding a state touches shared code" problem FR-005/SC-006 rule out.

## 6. Continuing `001`'s conventions

**Decision**: Same `src/` layout, same `pytest` testing framework, same `src/retirement_planner/<subpackage>/` pattern (this feature adds `tax/` alongside `scenario/`), same dataclass-first modeling style.

**Rationale**: No reason to deviate — `001` already established these as working conventions for this project, and Principle IV (Extensibility) is best served by every feature looking the same way at the top level.
