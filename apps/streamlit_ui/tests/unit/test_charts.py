"""Unit tests for src/rp_ui/charts.py -- fan chart (US2, T018) and the
engine-dependent comparison charts (US3, T024), against constructed
SummaryStatistics/percentile_bands-shaped fixtures matching 007's actual
to_jsonable() rendering (plan.md's Testing note; research.md §3).
"""

from rp_ui.charts import comparison_bar_chart, comparison_overlay_chart, fan_chart

PERCENTILE_BANDS = [
    {
        "plan_year": 1,
        "percentiles": [
            {"percentile": 0.10, "value": 1_000_000.0},
            {"percentile": 0.50, "value": 1_500_000.0},
            {"percentile": 0.90, "value": 2_000_000.0},
        ],
    },
    {
        "plan_year": 2,
        "percentiles": [
            {"percentile": 0.10, "value": 900_000.0},
            {"percentile": 0.50, "value": 1_600_000.0},
            {"percentile": 0.90, "value": 2_200_000.0},
        ],
    },
]


def test_fan_chart_has_one_trace_per_percentile():
    fig = fan_chart(PERCENTILE_BANDS)
    assert len(fig.data) == 3
    assert list(fig.data[0].x) == [1, 2]
    assert list(fig.data[1].y) == [1_500_000.0, 1_600_000.0]


def test_fan_chart_handles_empty_bands():
    fig = fan_chart([])
    assert len(fig.data) == 0


def test_fan_chart_yaxis_and_hover_use_currency_formatting():
    fig = fan_chart(PERCENTILE_BANDS)
    assert fig.layout.yaxis.tickformat == "$,.2f"
    assert fig.data[0].hovertemplate == "Plan year %{x}<br>%{y:$,.2f}<extra>%{fullData.name}</extra>"


def _simulated_summary(label: str) -> dict:
    return {
        "candidate_label": label,
        "success_rate": 0.92,
        "ending_balance": 1_500_000.0,
        "percentile_bands": PERCENTILE_BANDS,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 250_000.0,
        "unverified_figure_names": [],
    }


def _deterministic_summary(label: str) -> dict:
    return {
        "candidate_label": label,
        "success_rate": None,
        "ending_balance": 1_500_000.0,
        "percentile_bands": None,
        "median_depletion_age": None,
        "median_lifetime_tax_paid": 250_000.0,
        "unverified_figure_names": [],
    }


def test_comparison_overlay_chart_has_one_median_line_per_candidate():
    summaries = [_simulated_summary("SC"), _simulated_summary("FL")]
    fig = comparison_overlay_chart(summaries)
    assert len(fig.data) == 2
    assert fig.data[0].name == "SC"
    assert list(fig.data[0].y) == [1_500_000.0, 1_600_000.0]


def test_comparison_overlay_chart_yaxis_and_hover_use_currency_formatting():
    fig = comparison_overlay_chart([_simulated_summary("SC")])
    assert fig.layout.yaxis.tickformat == "$,.2f"
    assert fig.data[0].hovertemplate == "Plan year %{x}<br>%{y:$,.2f}<extra>%{fullData.name}</extra>"


def test_comparison_bar_chart_has_one_group_per_candidate():
    summaries = [_deterministic_summary("bracket_fill"), _deterministic_summary("no_conversion")]
    fig = comparison_bar_chart(summaries)
    labels = [trace.name for trace in fig.data]
    assert "ending_balance" in labels
    assert "median_lifetime_tax_paid" in labels
    assert list(fig.data[0].x) == ["bracket_fill", "no_conversion"]


def test_comparison_bar_chart_yaxis_and_hover_use_currency_formatting():
    summaries = [_deterministic_summary("bracket_fill")]
    fig = comparison_bar_chart(summaries)
    assert fig.layout.yaxis.tickformat == "$,.2f"
    assert fig.data[0].hovertemplate == "%{x}<br>%{y:$,.2f}<extra>%{fullData.name}</extra>"
