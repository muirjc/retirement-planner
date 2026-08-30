"""Reusable Streamlit-widget interaction helpers for Playwright.

Streamlit (1.38+) renders its selectbox/checkbox/radio widgets via
react-aria components, not plain HTML form controls -- a few interaction
patterns below aren't what a plain `<select>`/`<input type=checkbox>`
would need, so they're centralized here once (found by inspecting the
real rendered DOM against a running instance) rather than rediscovered
per test file.
"""

from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


def select_option(page: Page, label: str, value: str) -> None:
    """Streamlit's selectbox is a react-aria combobox: clicking it alone
    doesn't reliably open the option listbox in a headless browser --
    an ArrowDown keypress after the click does. Matched by role
    (get_by_role("combobox", ...)), not get_by_label(), since some labels
    (e.g. "State") also match an unrelated page heading via
    get_by_label()'s own aria-labelledby resolution."""
    combo = page.get_by_role("combobox", name=label, exact=True)
    combo.click()
    combo.press("ArrowDown")
    page.wait_for_timeout(200)
    page.get_by_role("option", name=value, exact=True).click()
    page.wait_for_timeout(300)


def fill_field(page: Page, label: str, value: object) -> None:
    """A text/number input -- these DO have a proper <label for=...>
    association, so get_by_label() alone resolves them."""
    field = page.get_by_label(label, exact=True)
    field.fill(str(value))
    field.blur()
    page.wait_for_timeout(200)


def toggle_checkbox(page: Page, label: str) -> None:
    """Streamlit's checkbox input is wrapped in a react-aria <label> that
    intercepts a plain click at the input's own coordinates in a headless
    browser -- force=True clicks through it, which is not bypassing
    anything a real user's mouse click on the visible checkbox wouldn't
    also land on (the wrapping label is the actual clickable surface)."""
    page.get_by_label(label, exact=True).click(force=True)
    page.wait_for_timeout(500)


def select_radio(page: Page, label: str) -> None:
    page.get_by_role("radio", name=label, exact=True).check(force=True)
    page.wait_for_timeout(500)


def wait_for_ready(page: Page) -> None:
    """Waits for at least one Streamlit widget label to be present --
    the generic "this page's script has finished its first run" signal
    every page in this app has, used right after page.goto()."""
    page.get_by_test_id("stWidgetLabel").first.wait_for(state="visible", timeout=15_000)


def wait_for_results(page: Page, *, timeout: int = 25_000) -> None:
    """Waits for a Run/Compare click's own rerun to fully finish, using
    Streamlit's own `stStatusWidget` running indicator rather than
    guessing which specific result element (chart, table, alert) happens
    to land in the DOM first -- those all appear together, atomically,
    once the rerun completes, but individually racing to wait for "the
    first one of chart/exception/alert to become visible" flaked: a
    plain-DOM alert can register as "visible" a tick before a Plotly
    chart's own canvas/SVG finishes painting, and a chart a tick before a
    later-rendered stDataFrame table, so whichever one this helper picked
    to wait for was never the one every caller actually goes on to
    assert against (found running this suite's own Monte Carlo cases,
    which take longer than Deterministic and so hit the race more
    often).

    The two-step wait (first try to observe stStatusWidget appear, then
    wait for it to disappear) handles both a rerun slow enough for this
    call to catch it starting and one already finished by the time this
    runs -- the first wait's own timeout is short and its failure is
    swallowed for exactly that "already done" case.
    """
    status = page.get_by_test_id("stStatusWidget")
    try:
        status.first.wait_for(state="visible", timeout=2_000)
    except PlaywrightTimeoutError:
        pass
    status.first.wait_for(state="hidden", timeout=timeout)
    # stStatusWidget disappearing reflects the script-execution/websocket
    # side finishing, not necessarily that the frontend's own React
    # re-render has fully painted the new elements yet -- a settle buffer
    # here avoids racing a caller's very next assertion against that last
    # bit of paint (found flaking under this suite's full run, never in
    # a quick isolated check of the same interaction).
    page.wait_for_timeout(1_500)
