"""Chart construction (data-model.md § Charts). Every function here takes
007's own response data, already shaped by `to_jsonable()`
(percentile_bands as a list of {plan_year, percentiles: [{percentile,
value}, ...]}) -- none of these functions computes a statistic of its
own; each is a display-shaping step over numbers 007 already returned
(Constitution Check's own "must never round, aggregate, or omit a field
in a way that changes its meaning" requirement).
"""

from __future__ import annotations

import plotly.graph_objects as go

_CURRENCY_TICKFORMAT = "$,.2f"
"""D3-format spec for a Plotly axis tick -- the `$` token is d3-format's own
currency-symbol type, so this natively renders comma-grouped dollars (e.g.
$1,234,567.89), unlike rp_ui.formatting.CURRENCY_INPUT_FORMAT's printf-style
constraint (see that module's docstring for why editable st.number_input
widgets can't get comma grouping)."""

_LINE_HOVERTEMPLATE = "Plan year %{x}<br>%{y:$,.2f}<extra>%{fullData.name}</extra>"
_BAR_HOVERTEMPLATE = "%{x}<br>%{y:$,.2f}<extra>%{fullData.name}</extra>"


def _percentile_label(percentile: float) -> str:
    return f"p{round(percentile * 100)}"


def fan_chart(percentile_bands: list[dict]) -> go.Figure:
    """One line per percentile, ending balance over plan year (User Story 2,
    Acceptance Scenario US2.1)."""
    fig = go.Figure()
    if not percentile_bands:
        return fig

    plan_years = [band["plan_year"] for band in percentile_bands]
    percentile_values = sorted({entry["percentile"] for band in percentile_bands for entry in band["percentiles"]})

    for percentile in percentile_values:
        y = [
            next((entry["value"] for entry in band["percentiles"] if entry["percentile"] == percentile), None)
            for band in percentile_bands
        ]
        fig.add_trace(
            go.Scatter(
                x=plan_years, y=y, mode="lines", name=_percentile_label(percentile),
                hovertemplate=_LINE_HOVERTEMPLATE,
            )
        )

    fig.update_layout(
        title="Projected ending balance by percentile",
        xaxis_title="Plan year",
        yaxis_title="Ending balance",
        yaxis=dict(tickformat=_CURRENCY_TICKFORMAT),
    )
    return fig


def comparison_overlay_chart(summaries: list[dict]) -> go.Figure:
    """One line per candidate, each candidate's own median (50th
    percentile) ending balance across plan years -- only valid when every
    summary's percentile_bands is populated (a Monte Carlo comparison,
    research.md §3). 3_Compare.py is what decides which chart function to
    call, by checking percentile_bands is not None first."""
    fig = go.Figure()
    for summary in summaries:
        bands = summary.get("percentile_bands") or []
        plan_years = [band["plan_year"] for band in bands]
        medians = [
            next((entry["value"] for entry in band["percentiles"] if entry["percentile"] == 0.50), None)
            for band in bands
        ]
        fig.add_trace(
            go.Scatter(
                x=plan_years, y=medians, mode="lines", name=summary.get("candidate_label") or "candidate",
                hovertemplate=_LINE_HOVERTEMPLATE,
            )
        )

    fig.update_layout(
        title="Median ending balance by candidate",
        xaxis_title="Plan year",
        yaxis_title="Median ending balance (50th percentile)",
        yaxis=dict(tickformat=_CURRENCY_TICKFORMAT),
    )
    return fig


def comparison_bar_chart(summaries: list[dict]) -> go.Figure:
    """One bar group per candidate, comparing ending_balance and
    median_lifetime_tax_paid -- the only scalar metrics a deterministic
    (004) candidate has (its percentile_bands is always None, so there is
    no per-year series to overlay, research.md §3)."""
    labels = [summary.get("candidate_label") or "candidate" for summary in summaries]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="ending_balance", x=labels, y=[summary["ending_balance"] for summary in summaries],
            hovertemplate=_BAR_HOVERTEMPLATE,
        )
    )
    fig.add_trace(
        go.Bar(
            name="median_lifetime_tax_paid",
            x=labels,
            y=[summary["median_lifetime_tax_paid"] for summary in summaries],
            hovertemplate=_BAR_HOVERTEMPLATE,
        )
    )
    fig.update_layout(
        title="Candidate comparison", barmode="group", yaxis=dict(tickformat=_CURRENCY_TICKFORMAT)
    )
    return fig
