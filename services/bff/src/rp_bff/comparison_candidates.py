"""Converts a comparison request's raw `candidates` list into the shape
004's/005's own compare_*() functions expect, per axis (research.md §7):
`state` and `claiming_age_grid` candidates pass through unchanged (a list
of state codes, and a list of {person_name: age} dicts respectively);
`roth_conversion_strategy` and `withdrawal_sequencing` candidates become
StrategyConfiguration instances.

For both StrategyConfiguration-shaped axes, the field the axis is NOT
varying (withdrawal_strategy for the conversion axis; the conversion
fields and claiming_ages for the sequencing axis) is filled with a
harmless placeholder -- every compare_*() function immediately overwrites
those fields via dataclasses.replace() with its own shared, held-fixed
value (004's/005's own compare.py), so the placeholder is never actually
used for anything.
"""

from __future__ import annotations

from typing import Any

from retirement_planner.comparison import StrategyConfiguration

_PLACEHOLDER_WITHDRAWAL_STRATEGY = "rmd_taxable_traditional_roth"
_PLACEHOLDER_CLAIMING_AGES: dict[str, int] = {}


def build_candidates_for_axis(
    axis: str, raw_candidates: list[Any], *, base_label: str
) -> list[StrategyConfiguration]:
    """Converts raw_candidates (JSON-decoded dicts from the request body)
    into StrategyConfiguration instances for the "roth_conversion_strategy"
    and "withdrawal_sequencing" axes. Raises ValueError for any other axis
    -- state/claiming_age_grid candidates pass through unchanged and never
    reach this function."""
    if axis == "roth_conversion_strategy":
        return [
            StrategyConfiguration(
                label=candidate.get("label") or f"{base_label}_{index}",
                withdrawal_strategy=_PLACEHOLDER_WITHDRAWAL_STRATEGY,  # overwritten by compare_*()
                conversion_strategy=candidate.get("conversion_strategy"),
                conversion_bracket_ceiling_or_amount=candidate.get("conversion_bracket_ceiling_or_amount"),
                conversion_window=_as_window(candidate.get("conversion_window")),
                claiming_ages=_PLACEHOLDER_CLAIMING_AGES,  # overwritten by compare_*()
            )
            for index, candidate in enumerate(raw_candidates)
        ]
    if axis == "withdrawal_sequencing":
        return [
            StrategyConfiguration(
                label=candidate.get("label") or f"{base_label}_{index}",
                withdrawal_strategy=candidate["withdrawal_strategy"],
                conversion_strategy=None,  # overwritten by compare_*()
                conversion_bracket_ceiling_or_amount=None,  # overwritten by compare_*()
                conversion_window=None,  # overwritten by compare_*()
                claiming_ages=_PLACEHOLDER_CLAIMING_AGES,  # overwritten by compare_*()
            )
            for index, candidate in enumerate(raw_candidates)
        ]
    raise ValueError(f"build_candidates_for_axis() does not handle axis {axis!r} (state/claiming_age_grid pass through unchanged)")


def _as_window(window: Any) -> tuple[int, int] | None:
    """Converts a JSON-decoded 2-element list (e.g. [2028, 2034]) into the
    tuple[int, int] StrategyConfiguration.conversion_window expects."""
    if window is None:
        return None
    return (window[0], window[1])
