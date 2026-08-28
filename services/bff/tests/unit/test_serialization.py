"""Unit tests for rp_bff.serialization.to_jsonable() (research.md §3):
date -> ISO string, dict[float, float] -> array-of-objects, tuple -> array,
and recursion through nested dataclasses.
"""

from dataclasses import dataclass
from datetime import date

from retirement_planner.simulation import PercentileBand
from retirement_planner.tax import FigureUsage


def test_date_field_becomes_iso_string():
    from rp_bff.serialization import to_jsonable

    figure = FigureUsage(name="f", citation="c", last_verified=date(2026, 8, 27), verified=False)

    result = to_jsonable(figure)

    assert result["last_verified"] == "2026-08-27"
    assert result["name"] == "f"
    assert result["verified"] is False


def test_float_keyed_dict_becomes_array_of_percentile_value_objects():
    from rp_bff.serialization import to_jsonable

    band = PercentileBand(plan_year=1, percentiles={0.10: 100.0, 0.50: 150.0, 0.90: 200.0})

    result = to_jsonable(band)

    assert result["plan_year"] == 1
    assert result["percentiles"] == [
        {"percentile": 0.10, "value": 100.0},
        {"percentile": 0.50, "value": 150.0},
        {"percentile": 0.90, "value": 200.0},
    ]


def test_tuple_field_becomes_json_array():
    from rp_bff.serialization import to_jsonable

    @dataclass
    class WithTuple:
        window: tuple[int, int]

    result = to_jsonable(WithTuple(window=(2028, 2034)))

    assert result["window"] == [2028, 2034]


def test_recurses_through_nested_dataclasses_and_lists():
    from rp_bff.serialization import to_jsonable

    @dataclass
    class Inner:
        last_verified: date

    @dataclass
    class Outer:
        items: list[Inner]

    result = to_jsonable(Outer(items=[Inner(last_verified=date(2026, 1, 1)), Inner(last_verified=date(2026, 6, 1))]))

    assert result == {"items": [{"last_verified": "2026-01-01"}, {"last_verified": "2026-06-01"}]}


def test_plain_scalars_pass_through_unchanged():
    from rp_bff.serialization import to_jsonable

    assert to_jsonable(42) == 42
    assert to_jsonable("text") == "text"
    assert to_jsonable(None) is None
    assert to_jsonable(3.14) == 3.14
