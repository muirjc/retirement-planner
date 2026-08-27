# Data Model: Federal & State Tax Calculation Engine

Source: [spec.md](./spec.md) Key Entities section. Types are described conceptually (Python `dataclasses`, per [research.md](./research.md)) — field names are illustrative, not a locked contract; the locked contract for downstream features is [contracts/tax-api.md](./contracts/tax-api.md).

This feature is a **pure calculator**: it does not validate that inputs are individually sensible (that's `001-scenario-config-management`'s job for the values it owns, and a future feature's job for whatever derives `IncomeComponents` from account activity). It only refuses to produce a result when it genuinely cannot — an unsupported tax year for a given figure (FR-016) — never because an income figure looks unusual.

## FilingStatus

An enum: `single` or `married_filing_jointly` — the same two values `001`'s `Household.filing_status` uses, kept independently here since this feature does not import from `scenario/`.

## IncomeComponents

| Field | Type | Notes |
|---|---|---|
| `ordinary_income` | number | Household-level pre-tax income subject to ordinary rates (e.g., traditional retirement account withdrawals, wages). Roth withdrawals are excluded by the caller before this figure is built — they're federally tax-free and never enter this calculation (Assumptions). |
| `social_security_gross_benefit` | number | Household-level gross Social Security benefit before any taxability determination. |

**No sign/range validation is performed here** — a negative or implausible value is passed through as given; catching that is the responsibility of whatever feature produces these numbers (see spec.md Assumptions).

## FilerAges

A list of filer ages (one per household member) — length **must** be 1 for `single` or 2 for `married_filing_jointly`, mirroring `001`'s `Household.members` count rule (data-model.md § Household). A mismatched length is a shape error the caller made, not a value the engine can compute against — the engine raises rather than guessing which age applies to which slot.

## TaxYear

A plain integer (e.g., `2026`). No entity wrapper — every function that needs a tax year takes one directly.

## SourcedFigure

The auditability primitive (FR-009). Generic over the figure's value type — a flat exclusion amount is `SourcedFigure[float]`; a full bracket table is `SourcedFigure[BracketTable]` (see below). One `SourcedFigure` corresponds to one real-world citation (e.g., "SC Code §12-6-510" or "IRS Rev. Proc. 2025-XX") — a state's whole bracket table for a year is one citable publication, not one citation per row.

| Field | Type | Notes |
|---|---|---|
| `schedule` | dict[int, T] | Tax year → value in effect that year. Every figure has at least one entry, even if it has never changed. |
| `citation` | string | Source reference (statute section, IRS publication number, etc.). |
| `last_verified` | date | When this figure was last confirmed against the citation. |
| `verified` | boolean | `True` only if a human has actually cross-checked this figure against its citation (Development Workflow gate in plan.md) — defaults to `False` for every figure shipped with this feature unless explicitly confirmed during implementation. |

**Behavior**: looking up `schedule[tax_year]` for a year not present in `schedule` raises `UnsupportedTaxYearError` (FR-016) — it never falls back to the nearest year or interpolates.

## BracketTable / BracketRow

The value type used by graduated-bracket figures (federal, SC, DE).

| BracketRow field | Type | Notes |
|---|---|---|
| `rate` | number | The marginal rate for this bracket, e.g. `0.03` for 3%. |
| `income_up_to` | number \| null | Upper edge of this bracket's income range; `null` means "and above" (the top bracket). |

A `BracketTable` is an ordered list of `BracketRow`s, lowest bracket first.

## FigureUsage

One entry in a result's provenance trail (FR-010, FR-011) — a snapshot of one `SourcedFigure`'s citation metadata *for the year actually used*, not the figure's whole schedule.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Stable, human-readable identifier for which figure this is (e.g., `"federal_mfj_brackets"`, `"sc_age_65_exclusion"`). |
| `citation` | string | Copied from the `SourcedFigure` used. |
| `last_verified` | date | Copied from the `SourcedFigure` used. |
| `verified` | boolean | Copied from the `SourcedFigure` used — this is what lets a caller tell, per figure, whether it's confirmed (FR-011). |

## FederalTaxResult

| Field | Type | Notes |
|---|---|---|
| `federal_tax_owed` | number | The computed federal tax liability. |
| `taxable_social_security` | number | How much of `social_security_gross_benefit` was included in taxable income (FR-002) — always between `0` and `social_security_gross_benefit × 0.85` inclusive. |
| `figures_used` | list[FigureUsage] | Every figure this computation drew on (FR-010). |

## StateTaxResult

| Field | Type | Notes |
|---|---|---|
| `state` | string | The two-letter state code this result is for. |
| `state_tax_owed` | number | The computed state tax liability. `0` for a zero-income-tax state (FR-007). |
| `figures_used` | list[FigureUsage] | Every figure this state's module drew on (FR-010) — empty for a zero-tax state, since FR-007 says it must not require any figures. |

## UnsupportedTaxYearError *(not a data entity — the refusal signal from FR-016)*

Raised instead of returning a result when a requested tax year isn't in a figure's schedule.

| Field | Type | Notes |
|---|---|---|
| `figure_name` | string | Which figure couldn't be resolved. |
| `requested_year` | int | The year that was asked for. |
| `available_years` | list[int] | The years that *are* documented for this figure, so the error is actionable. |

## Relationships

- `FederalTaxResult` and `StateTaxResult` are independent — computing one never requires or mutates the other (Acceptance Scenario US2.4).
- Every `SourcedFigure` used to build a `FederalTaxResult` or `StateTaxResult` contributes exactly one `FigureUsage` entry to that result — a figure consulted but not ultimately used to compute the number reported (e.g., a bracket row above the household's income) does not appear in `figures_used`.
- State modules do not share `SourcedFigure` instances with each other or with the federal module — each module owns its own figures (FR-005), even where two states happen to use the same numeric value.

## State transitions

None — every computation is stateless. A `FederalTaxResult` or `StateTaxResult` is produced fresh from its inputs each call; nothing is persisted (this feature has no storage layer, unlike `001`'s scenario store).
