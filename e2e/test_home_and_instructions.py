"""Home page and Instructions page: the two pages with no form to drive,
just confirming they render and (for Home) that the backend connection
check succeeds against this suite's own isolated BFF instance."""

from __future__ import annotations


def test_home_page_connects_to_the_backend(page, e2e_stack):
    page.goto(e2e_stack.ui_base_url, timeout=30_000)
    page.get_by_text("Connected to the backend.").wait_for(state="visible", timeout=15_000)
    assert not page.get_by_test_id("stException").count()


def test_instructions_page_renders_every_section(page, e2e_stack):
    page.goto(f"{e2e_stack.ui_base_url}/Instructions", timeout=30_000)
    page.get_by_role("heading", name="Inherited IRA (Optional)").wait_for(state="visible", timeout=15_000)
    assert not page.get_by_test_id("stException").count()
    # rp-c8b/rp-iju/rp-l4d: the Instructions copy was rewritten for
    # 013-inherited-ira-edge-cases -- confirm the page that actually
    # renders it doesn't error, and the new content is really there.
    assert page.get_by_text("eligible-designated-beneficiary").count() > 0
