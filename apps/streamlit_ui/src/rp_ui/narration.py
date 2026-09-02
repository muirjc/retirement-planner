"""Plain-language explanation of a result's numbers (rp-r07): a
non-technical user viewing Run Simulation or Compare results needs, next
to each chart, the specific numbers it's built from and a plain-language
explanation of how each was computed -- not a wall of methodology, just
enough to make an informed decision without understanding the simulation
engine, tax code, or withdrawal-strategy mechanics.

Templated, not AI-generated (rp-r07's own design decision for v1):
deterministic text built entirely from 007's own SummaryStatistics JSON
shape, already returned by every Run Simulation/Compare request -- no new
dependency, no API key, no per-request cost/latency, and no hallucination
risk for numbers presented as financial-decision support. AI-generated
narration remains a possible follow-on layered on top of this same
narrate_metrics() shape, not a replacement for it.

narrate_metrics()/render_results_explanation() splits pure text-building
from Streamlit rendering exactly the way formatting.py (pure)/
verification.py (rendering) already do, so narrate_metrics() stays
unit-testable without a running Streamlit script context. Deliberately
does not duplicate render_verification_indicator()'s own unverified-figure
reporting -- narrate_metrics() instead points at it by name, so there is
exactly one place that lists which figures are unverified.
"""

from __future__ import annotations

import streamlit as st

from .formatting import format_currency


def narrate_metrics(summary: dict, *, path_count: int | None = None) -> list[dict[str, str]]:
    """Builds one entry per metric present in `summary` (007's own
    SummaryStatistics JSON shape: success_rate, ending_balance,
    percentile_bands, median_depletion_age, median_lifetime_tax_paid,
    median_lifetime_irmaa_paid, median_lifetime_niit_paid), each a
    {"label", "value", "explanation"} dict. Whether summary came from the
    Monte Carlo or deterministic engine is read from success_rate being
    present or None (SummaryStatistics' own documented convention,
    reporting/models.py) -- never passed as a separate flag. A metric is
    only skipped when its own underlying value is None (e.g.
    median_depletion_age when nothing ever depleted).

    path_count, when given, lets the success-rate entry read "N of M
    paths" instead of just a percentage -- Run Simulation always knows it
    (its response includes every path's own result); Compare's simulated
    engine does not expose a path count in its response, so its entries
    fall back to percentage-only, never a guessed or fabricated count.
    """
    is_monte_carlo = summary.get("success_rate") is not None
    entries: list[dict[str, str]] = []

    if is_monte_carlo:
        rate = summary["success_rate"]
        if path_count:
            successes = round(rate * path_count)
            value = f"{rate * 100:.1f}% ({successes} of {path_count} simulated paths)"
        else:
            value = f"{rate * 100:.1f}% of simulated paths"
        entries.append(
            {
                "label": "Success rate",
                "value": value,
                "explanation": (
                    "Each simulated path applies its own randomly-drawn sequence of market "
                    "returns to this plan. A path “succeeds” if spending is fully funded "
                    "every year through the end of the plan horizon, with no shortfall. The "
                    "success rate is simply the share of paths that succeeded."
                ),
            }
        )
        entries.append(
            {
                "label": "Ending balance (median)",
                "value": format_currency(summary.get("ending_balance")),
                "explanation": (
                    "The middle (50th percentile) total account balance across all simulated "
                    "paths, in the plan's final year -- half the simulated paths ended with "
                    "more, half with less. See the percentile chart above for the full spread."
                ),
            }
        )
    else:
        entries.append(
            {
                "label": "Ending balance",
                "value": format_currency(summary.get("ending_balance")),
                "explanation": (
                    "The projected total account balance in the plan's final year, under this "
                    "engine's single fixed assumed rate of return -- not a range of outcomes, "
                    "since the deterministic engine runs the plan through exactly once."
                ),
            }
        )

    if summary.get("median_depletion_age") is not None:
        if is_monte_carlo:
            entries.append(
                {
                    "label": "Median depletion age",
                    "value": f"{summary['median_depletion_age']:.0f}",
                    "explanation": (
                        "Among the simulated paths that ran out of money before the plan "
                        "horizon ended, the middle age at which that first happened."
                    ),
                }
            )
        else:
            entries.append(
                {
                    "label": "Depletion age",
                    "value": f"{summary['median_depletion_age']:.0f}",
                    "explanation": "The age at which this projection first fell short of covering that year's spending need.",
                }
            )

    tax_qualifier = "The median, across simulated paths, of the" if is_monte_carlo else "This projection's"
    entries.append(
        {
            "label": "Lifetime tax paid",
            "value": format_currency(summary.get("median_lifetime_tax_paid")),
            "explanation": f"{tax_qualifier} total federal and state income tax paid over the full plan horizon.",
        }
    )
    entries.append(
        {
            "label": "Lifetime Medicare IRMAA surcharge",
            "value": format_currency(summary.get("median_lifetime_irmaa_paid")),
            "explanation": (
                f"{tax_qualifier} total Medicare Income-Related Monthly Adjustment Amount "
                "surcharge -- an extra premium charged when income in a prior year was high "
                "enough to trigger it."
            ),
        }
    )
    entries.append(
        {
            "label": "Lifetime Net Investment Income Tax",
            "value": format_currency(summary.get("median_lifetime_niit_paid")),
            "explanation": (
                f"{tax_qualifier} total 3.8% Net Investment Income Tax paid -- an additional "
                "federal tax on investment income above a threshold."
            ),
        }
    )
    entries.append(
        {
            "label": "Lifetime early-withdrawal penalty paid",
            "value": format_currency(summary.get("median_lifetime_early_withdrawal_penalty_paid")),
            "explanation": (
                f"{tax_qualifier} total 10% early-withdrawal penalty paid -- an additional tax on "
                "Traditional or unseasoned Roth-conversion withdrawals taken before age 59½."
            ),
        }
    )
    entries.append(
        {
            "label": "Lifetime FICA payroll tax paid",
            "value": format_currency(summary.get("median_lifetime_fica_tax_paid")),
            "explanation": (
                f"{tax_qualifier} total employee-side FICA payroll tax (Social Security + Medicare) "
                "on any earned-income streams (e.g. phased-retirement wages) -- $0 for a household "
                "with only pensions, annuities, or account withdrawals, since those are not wages."
            ),
        }
    )

    if is_monte_carlo:
        entries.append(
            {
                "label": "Percentile bands (chart above)",
                "value": "10th / 25th / 50th / 75th / 90th percentile, each plan year",
                "explanation": (
                    "At each plan year, every simulated path's total account balance is sorted "
                    "and these five points are read off -- e.g. the 10th percentile line is the "
                    "balance only 10% of paths fell below that year. The gap between the bands "
                    "shows how much outcomes vary, not just their average."
                ),
            }
        )

    return entries


def render_results_explanation(summary: dict, *, path_count: int | None = None, title: str | None = None) -> None:
    """Renders narrate_metrics()'s entries in a collapsed expander,
    directly under the chart/table it explains -- collapsed by default so
    it doesn't compete with those for attention, available on demand for a
    user who wants to know how a number was arrived at (rp-r07). `title`
    (e.g. a candidate_label) distinguishes multiple expanders on the same
    page (Compare's one-per-candidate case) -- omitted on Run Simulation's
    single-result page, where it would be redundant."""
    entries = narrate_metrics(summary, path_count=path_count)
    label = f"How were these numbers computed? — {title}" if title else "How were these numbers computed?"
    with st.expander(label):
        for entry in entries:
            st.markdown(f"**{entry['label']}:** {entry['value']}")
            st.caption(entry["explanation"])
