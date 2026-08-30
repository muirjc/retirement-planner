# Phase 1 Data Model: Figure Verification (Placeholder Tax Figures)

## No new or changed entities

This feature introduces no new entity and changes no existing entity's
*shape*. `SourcedFigure[T]` (defined in `002-tax-calculation-engine`'s
[data-model.md](../002-tax-calculation-engine/data-model.md#sourcedfigure))
keeps its existing four fields — `schedule: dict[int, T]`, `citation:
str`, `last_verified: date`, `verified: bool` — untouched. `FigureUsage`,
`FederalTaxResult`, `IrmaaResult`, `NiitResult`, `HsaEligibility`, and
`RmdResult` are likewise untouched: none of their fields or types change.

What this feature changes is the *data inside* 8 existing `SourcedFigure`
instances — literal values, citation strings, `last_verified` dates, and
`verified` flags — and, for one of them, the *shape of that instance's
`schedule` dict* (still `dict[int, T]`, just built from two ranges
instead of one). No consumer of `SourcedFigure` needs to change to
accommodate this.

## The 8 figure instances this feature touches

| Instance | File | `T` | Change |
|---|---|---|---|
| `niit_rate` | `tax/niit.py` | `float` | Citation + `verified` only. |
| `niit_threshold_mfj` | `tax/niit.py` | `float` | Citation + `verified` only. |
| `niit_threshold_single` | `tax/niit.py` | `float` | Citation + `verified` only. |
| `ss_provisional_income_thresholds_mfj` | `tax/social_security.py` | `_ProvisionalIncomeThresholds` (2-field dataclass) | Citation + `verified` only. |
| `ss_provisional_income_thresholds_single` | `tax/social_security.py` | `_ProvisionalIncomeThresholds` | Citation + `verified` only. |
| `federal_brackets_mfj` | `tax/federal.py` | `BracketTable` (tuple of `BracketRow`) | Literal thresholds corrected to a named year's published figures; citation + `verified`. |
| `federal_brackets_single` | `tax/federal.py` | `BracketTable` | Same. |
| `irmaa_tiers_mfj` | `tax/irmaa.py` | `IrmaaTierTable` (tuple of `IrmaaTierRow`) | Literal thresholds/surcharges corrected to a named year's published figures; citation + `verified`. |
| `irmaa_tiers_single` | `tax/irmaa.py` | `IrmaaTierTable` | Same. |
| `hsa_contribution_limits` | `mechanics/hsa.py` | `_HsaLimits` (3-field dataclass) | Literal figures confirmed/corrected against a named year's Rev. Proc.; citation + `verified`. |
| `uniform_lifetime_table` | `mechanics/rmd.py` | `dict[int, float]` (age → divisor) | Existing divisors (ages 72-100) cross-checked and corrected where wrong; coverage extended through IRS Pub. 590-B's full published age range; citation + `verified`. |
| `rmd_start_age` | `mechanics/rmd.py` | `int` | **Schedule shape change** (below); citation + `verified`. |

12 rows above cover the 8 figure *names* the epic tracks — `niit_rate`
plus the two `niit_threshold_*` names are 3 separate `SourcedFigure`
instances backing what the epic's own description groups under one
label (`niit_threshold_mfj`/`niit_threshold_single`), matching how the
source code already structures them.

## `rmd_start_age`'s schedule shape, before and after

**Before** (current code, `mechanics/rmd.py`):

```python
RMD_START_AGE: SourcedFigure[int] = SourcedFigure(
    name="rmd_start_age",
    schedule={year: 73 for year in _DOCUMENTED_YEARS},
    ...
)
```

One flat value, `73`, repeated across every documented year (2020-2074).

**After**:

```python
RMD_START_AGE: SourcedFigure[int] = SourcedFigure(
    name="rmd_start_age",
    schedule={
        **{year: 73 for year in range(2020, 2033)},
        **{year: 75 for year in range(2033, 2075)},
    },
    ...
)
```

Still a `dict[int, int]` — the same `schedule: dict[int, T]` field every
`SourcedFigure` already has, and the same `.value_for_year(tax_year)`
lookup mechanism (`tax/models.py`) already used by every other figure.
`compute_rmd()`'s call site (`RMD_START_AGE.value_for_year(tax_year)`,
`mechanics/rmd.py`) needs no change — it already looks up by `tax_year`,
which is exactly the axis this schedule now varies on.

## `uniform_lifetime_table`'s coverage, before and after

**Before**: `_UNIFORM_LIFETIME_DIVISORS` covers ages 72-100 (29 entries).
A household member's RMD computed at age 101+ (with no spouse-beneficiary
exception routing to the joint-life table) raises a `KeyError` today —
not a typed `UnsupportedTaxYearError`, since the age lookup
(`table_figure.value_for_year(tax_year)[member_age]`, `mechanics/rmd.py`)
is a second, un-typed dict index *inside* an already-resolved year's
table, distinct from the `SourcedFigure`-level year lookup that does
raise `UnsupportedTaxYearError`.

**After**: `_UNIFORM_LIFETIME_DIVISORS` covers every age IRS Pub. 590-B
Table III publishes (through 120, mirroring `SINGLE_LIFE_EXPECTANCY_TABLE`'s
own 0-120+ extension under `rp-6c5`). The un-typed `KeyError` behavior for
an age beyond even that extended range is unchanged by this feature
(spec.md Edge Cases: "this feature only shrinks how often that gap is
hit") — closing that gap entirely, if ever needed, is separate follow-on
work, not something this feature's scope covers.
