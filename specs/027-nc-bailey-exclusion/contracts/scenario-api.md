# Contract: `retirement_planner.scenario` public API (addendum to `001`, `010`, `016`, `017`, `018`, `021`)

Extends `specs/021-pension-annuity-income/contracts/scenario-api.md` with one additive field.
`parse_scenario()`, `validate()`, `save_scenario()`, `list_scenarios()`, `load_scenario()`,
`delete_scenario()` keep their existing locked signatures — every existing field of every existing
type is unchanged.

## Modified data type (`models`)

```python
@dataclass
class IncomeStream:
    label: str
    stream_type: Literal["pension", "annuity", "earned_income"]
    start_age: int
    annual_amount: float
    inflation_adjustment: Literal["cola_adjusted", "fixed_nominal"]
    end_age: int | None = None
    bailey_qualifying: bool = False   # NEW — this feature
```

`bailey_qualifying`: household attestation that this stream is a North Carolina Bailey-settlement-
qualifying government/military retirement benefit (data-model.md). Defaults to `False` — every
scenario YAML written before this feature parses to the same `IncomeStream` it did before.

## Modified operation (`loader._build_income_stream`)

Reads an optional `"bailey_qualifying"` key from the stream mapping (`data.get("bailey_qualifying",
False)`, same optional-field discipline as `end_age`) — absent, `null`, or `false` all parse to
`False`. Not one of `_require()`'s required fields; no new `ScenarioParseError` case.

## Modified operation (`store._income_stream_to_dict`)

Round-trips `"bailey_qualifying": stream.bailey_qualifying` alongside every other existing
`IncomeStream` field — same discipline every other field already follows.

## Unmodified (`validation.validate`)

No new validation rule. `bailey_qualifying` is an unconstrained boolean (data-model.md
"Validation"); the existing per-stream `end_age`/`annual_amount` blocking checks are unchanged.

## Consumption expectations for downstream features

- `comparison.projection` sums `bailey_qualifying=True` streams' amounts into
  `IncomeComponents.government_pension_income` (`comparison-api.md` addendum, this feature).
- No other existing consumer of `IncomeStream` (`mechanics.income_streams.
  compute_income_stream_amount()`, `reporting.account_attribution`) reads `bailey_qualifying` —
  unaffected.
