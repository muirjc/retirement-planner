"""Shared currency-display formatting for the Streamlit UI.

Two distinct cases, because they have genuinely different capabilities:

- **Editable `st.number_input` widgets** (account balances, spending, SS
  benefit, conversion bracket/amount) get no `$`/comma formatting at all --
  confirmed empirically against this project's installed Streamlit version
  (`streamlit.elements.widgets.number_input`): the widget validates its
  `format` string by computing `float(format % 2)`, so *any* non-numeric
  character in the format -- a `$` prefix, a comma, anything -- raises
  `StreamlitInvalidNumberFormatError` before the page even renders. There is
  no `format=` string that can show a currency symbol on an editable input
  in this Streamlit version. The realistic, actually-working substitute is a
  `($)` suffix on the widget's own label text (e.g. `"Traditional balance
  ($)"`), applied directly at each call site -- not a format string, so
  there's no shared constant for it here. Floats already default to two
  decimal places (`"%0.2f"`) with no `format=` argument at all, so nothing
  is lost by not passing one.
- **Display-only values** (table cells, plain text) use `format_currency()`,
  a normal Python f-string with full `$1,234.56`-style comma grouping --
  nothing prevents full formatting once a widget doesn't need to stay
  editable.

Plotly chart axes/hover (`charts.py`) use their own D3-format-spec
`tickformat`/`hovertemplate` strings, which *do* support comma grouping
natively -- see `charts.py`'s own `_CURRENCY_TICKFORMAT`.
"""

from __future__ import annotations


def format_currency(value: float | int | None) -> str:
    """Full `$1,234.56`-style formatting for a display-only (non-editable)
    dollar amount. Returns "n/a" for `None`, matching this app's existing
    convention for an absent metric (e.g. `2_Run_Simulation.py`'s
    success_rate handling)."""
    if value is None:
        return "n/a"
    return f"${value:,.2f}"
