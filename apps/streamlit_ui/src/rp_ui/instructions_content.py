"""Guidance content for pages/0_Instructions.py -- data-model.md § Section,
contracts/ui-pages.md § pages/0_Instructions.py.

A plain, hardcoded data structure, not user-editable config (spec.md's own
Assumptions rule that out) and not something this module computes --
every example figure or rule of thumb here is deliberately framed as an
example, never as an authoritative value this tool computed (Constitution
Check, Principle I). This module imports nothing from rp_ui.api_client,
retirement_planner, or rp_bff -- see
tests/integration/test_dependency_containment.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    """One guidance section. `body` is Markdown, rendered via st.markdown()."""

    title: str
    body: str


SECTIONS: list[Section] = [
    # Rendered by pages/0_Instructions.py in this order, one Section per
    # required field-group (data-model.md's table -- FR-002 through FR-007):
    Section(
        title="Household",
        body=(
            "For each party (each adult in the household), gather: their name or a short "
            "label, their current age, the Social Security claiming age you're planning "
            "around, and their estimated annual Social Security benefit **at that specific "
            "claiming age** -- not the amount shown for full retirement age if you plan to "
            "claim earlier or later. The Social Security Administration's own benefit "
            "estimator lets you check the amount for a specific age; a benefit figure that "
            "doesn't match the claiming age you enter is the most common mistake here."
        ),
    ),
    Section(
        title="Accounts",
        body=(
            "Gather each party's **own balance** for each account type they hold: traditional "
            "(pre-tax IRA/401(k) balances), Roth, and taxable. These are entered per person, "
            "not combined -- if both partners have a traditional IRA, enter each one under "
            "that partner's own row rather than adding them together. This matters beyond "
            "bookkeeping: Required Minimum Distributions are calculated per person, from that "
            "person's own age and own balance, so a combined number would misstate them for "
            "any household where the two ages or balances differ."
        ),
    ),
    Section(
        title="Spending",
        body=(
            "Enter your annual spending need in **today's dollars** -- what it would cost "
            "to live your planned lifestyle right now, not a number you've already "
            "inflated forward to some future year. Enter it **before taxes**; the tool "
            "calculates the taxes owed on top of this figure itself."
        ),
    ),
    Section(
        title="State",
        body=(
            "Enter the state you plan to reside in for tax purposes. The scenario form's "
            "own State dropdown always reflects the current list of supported states -- "
            "check it there rather than assuming a specific list, since new states are "
            "added over time."
        ),
    ),
    Section(
        title="Market Assumptions",
        body=(
            "These are your own forward-looking planning inputs, not a fact the tool "
            "looks up or verifies -- nobody can know future market returns in advance. "
            "If you're unsure where to start, a 60/40 stock/bond allocation with "
            "conservative real (inflation-adjusted) return assumptions is a defensible "
            "**example**, not a recommendation or the \"right\" answer."
        ),
    ),
    Section(
        title="Simulation Settings",
        body=(
            "**Paths** is how many randomized future scenarios are simulated -- more "
            "paths give a smoother, more stable success-rate estimate at the cost of a "
            "slower run. **Seed** fixes the randomness so re-running with the same inputs "
            "reproduces the same result -- useful for checking that a change you made, "
            "not random chance, caused a different outcome. **Plan to age** is the "
            "horizon the simulation runs until, not a prediction of how long you'll live."
        ),
    ),
    Section(
        title="Roth Conversion (Optional)",
        body=(
            "Leave this unchecked if you don't plan to convert traditional balances to "
            "Roth. If you do, the **window** is the range of plan years during which the "
            "conversion strategy is active -- outside that window, no conversions happen "
            "under this strategy."
        ),
    ),
]
