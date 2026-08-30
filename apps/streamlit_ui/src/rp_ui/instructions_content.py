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
    # required field-group (data-model.md's table -- FR-002 through FR-007),
    # plus Run Simulation and Compare -- every dropdown's option set gets an
    # explicit, per-option explanation here, not just a widget label
    # (each dropdown's live source of truth stays the widget itself; this
    # content explains what each already-listed option does):
    Section(
        title="Household",
        body=(
            "**Filing status** determines how many people you'll enter and drives which federal "
            "tax brackets apply. It offers two options:\n\n"
            "- **`single`** -- one person. Only Member 1's fields appear.\n"
            "- **`married_filing_jointly`** -- two people. Member 2's fields (and Member 2's own "
            "account balances, below) appear once you pick this.\n\n"
            "For each party (each adult in the household), gather: their name or a short "
            "label, their current age, the Social Security claiming age you're planning "
            "around, their **full retirement age (FRA)** -- typically 66-67 depending on "
            "birth year -- and their **Primary Insurance Amount (PIA)**: the annual Social "
            "Security benefit payable if claimed exactly at that FRA, not the (possibly "
            "reduced or increased) amount actually paid at the claiming age you enter. The "
            "tool derives the claiming-age-adjusted amount from the PIA and FRA together, so "
            "entering the PIA at the wrong age (or the FRA-adjusted amount you'd actually "
            "receive) is the most common mistake here -- the Social Security Administration's "
            "own benefit estimator shows both the FRA amount and the amount for a specific "
            "claiming age; use the FRA amount here. If you don't yet know your real FRA, "
            "leaving this field at its default (equal to your claiming age) is a safe "
            "fallback -- it simply means the tool won't reduce or increase the entered amount "
            "for claiming early or late."
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
            "added over time.\n\n"
            "States differ from each other in three ways that matter for this tool's numbers: "
            "whether they tax income at all (some have no state income tax, and always compute "
            "$0 owed), whether they use a flat rate or graduated brackets, and whether they "
            "offer an age-based exclusion that shields part of a retiree's income once they "
            "reach a certain age. If two states in the dropdown produce very different results "
            "for the same scenario, one of these three differences is almost always why -- and "
            "every bracket, rate, and exclusion figure behind them is only as accurate as its "
            "own verification status (see the unverified-figure indicator after you run)."
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
            "under this strategy.\n\n"
            "**Conversion strategy** offers two options, and each interprets the **Bracket "
            "ceiling or amount** field differently:\n\n"
            "- **`fill_to_bracket`** -- treats the field as an **income ceiling in dollars**. "
            "Each year in the window, it converts just enough of the traditional balance to "
            "bring that year's taxable income (ordinary income plus the taxable portion of "
            "Social Security) up to the ceiling, without going over -- never more than the "
            "traditional balance actually has. Use this to \"fill up\" a specific tax bracket "
            "every year without spilling into the next one.\n"
            "- **`fixed_amount`** -- treats the field as a **flat dollar amount to convert**. "
            "Each year in the window it converts exactly that amount (or whatever's left in "
            "the traditional balance, if less), regardless of income, Social Security, or "
            "which tax bracket that lands in.\n\n"
            "If you're unsure which to pick: `fill_to_bracket` targets a tax outcome and "
            "adapts the dollar amount each year to hit it; `fixed_amount` targets a dollar "
            "amount and lets the tax outcome fall where it falls."
        ),
    ),
    Section(
        title="Inherited IRA (Optional)",
        body=(
            "Leave this unchecked unless you (or one of the household members) inherited a "
            "traditional or Roth IRA from someone who has died. This tool computes:\n\n"
            "- **The SECURE 2.0 10-year rule** (a non-spouse, non-eligible-designated "
            "beneficiary): the account must be fully distributed by the 10th year after "
            "death. If the original owner had already begun their own RMDs, an annual "
            "required distribution is also due every year of that window; if they hadn't "
            "(or the account is Roth -- see below), no annual distribution is required at "
            "all, only the year-10 deadline.\n"
            "- **The eligible-designated-beneficiary (EDB) \"stretch\"** (a spouse, a minor "
            "child, a disabled/chronically-ill beneficiary, or someone not more than 10 "
            "years younger than the owner): an annual required distribution based on life "
            "expectancy instead, with no 10-year deadline of its own -- a spouse's own "
            "amount is recalculated fresh every year; a non-spouse's is reduced by 1.0 each "
            "year from an initial lookup. A minor child converts to the 10-year rule (a "
            "fresh 10-year clock) once they turn 21.\n\n"
            "**Not yet supported**: a trust or entity beneficiary -- picking that "
            "relationship will block the scenario.\n\n"
            "- **Account type** -- traditional or Roth. A Roth account's original owner is "
            "always treated as having died before their own required beginning date (RBD), "
            "regardless of the checkbox below -- Roth owners never have RMDs during their "
            "own lifetime.\n"
            "- **Beneficiary** -- which household member inherited it; that's who it's taxed "
            "to.\n"
            "- **Balance** -- the inherited account's own balance. It's tracked completely "
            "separately from that same person's own traditional balance above -- inherited "
            "money is never legally combined with an account you own outright, and this tool "
            "keeps them just as separate.\n"
            "- **Decedent's death year** and **Decedent's age at death** -- together these "
            "drive the required-distribution amount each year.\n"
            "- **Original owner had already begun their own RMDs before death** -- ignored "
            "for a Roth account (above). For a traditional account, this picks which of the "
            "two rules above applies, and, for an EDB, whether their annual amount is based "
            "on the longer of their own or the owner's life expectancy (checked) or their "
            "own alone (unchecked).\n"
            "- **Beneficiary relationship** -- `trust_or_entity` blocks the scenario; "
            "`minor_child` (paired with classification `eligible_designated_beneficiary_other`) "
            "triggers the age-21 conversion above; otherwise descriptive only.\n"
            "- **Beneficiary classification** -- `non_eligible_designated_beneficiary` for "
            "the 10-year rule, or `eligible_designated_beneficiary_spouse`/`_other` for the "
            "stretch.\n\n"
            "This form supports one inherited account. A household member with more than one "
            "inherited IRA (from different original owners) needs the scenario's saved file "
            "edited directly for the second one."
        ),
    ),
    Section(
        title="Run Simulation",
        body=(
            "Pick a saved scenario from **Scenario**, choose a **Withdrawal strategy**, and set "
            "**Reference tax year**, **Start plan year**, and **Start tax year** for this run.\n\n"
            "**Withdrawal strategy** controls the order accounts are drawn from to cover spending "
            "*after* any Required Minimum Distribution is taken -- the RMD itself always comes out "
            "of the traditional balance first, unconditionally, under either option:\n\n"
            "- **`rmd_taxable_traditional_roth`** (the default) -- after the RMD, spends from "
            "**taxable**, then **traditional**, then **Roth** last. Keeps tax-advantaged balances, "
            "especially Roth, growing untouched for as long as possible.\n"
            "- **`rmd_traditional_taxable_roth`** -- after the RMD, spends from **traditional** "
            "first, then **taxable**, then **Roth** last. Draws down pre-tax money sooner, which "
            "can mean higher taxable income in earlier years.\n\n"
            "Neither option ever draws more from an account than it holds -- an unmet need shows "
            "up as a reported shortfall rather than a negative balance.\n\n"
            "Always replace the reference tax year with a real calendar year before running -- an "
            "unedited placeholder value is the most common mistake on this page, and it won't fail "
            "as obviously as a blank field would. To use different **Paths**, **Seed**, or **Plan to "
            "age** than the scenario's own saved Simulation Settings, open **Advanced overrides** and "
            "check **Override scenario defaults** first; the fields inside are otherwise ignored even "
            "if you've changed them. Clicking **Run** shows a success-rate metric and a fan chart -- "
            "the spread of possible ending balances by plan year, one line per percentile -- and any "
            "error points back to what needs fixing, often on the Scenarios page itself."
        ),
    ),
    Section(
        title="Compare",
        body=(
            "Pick a scenario, an **Engine**, and an **Axis** to see how one changing input affects "
            "the outcome, holding everything else fixed across candidates.\n\n"
            "**Engine** has two options:\n\n"
            "- **Monte Carlo** -- runs the full randomized simulation (the same kind Run Simulation "
            "does) for every candidate, so results include a success rate and a percentile fan "
            "chart.\n"
            "- **Deterministic** -- runs one fixed-return projection per candidate instead (no "
            "randomness), so results show a single ending balance and tax total per candidate "
            "rather than a success rate. Faster, but doesn't answer \"how often does this work.\"\n\n"
            "**Axis** picks what varies between candidates -- the option list narrows to what the "
            "chosen Engine actually supports (Deterministic never offers `state`, since there's no "
            "single-run equivalent of a probabilistic location comparison):\n\n"
            "- **`state`** -- same scenario, different states of residence (Monte Carlo only). Each "
            "candidate is just a state picked from the same dropdown described under **State** "
            "above.\n"
            "- **`roth_conversion_strategy`** -- same scenario, different Roth conversion setups. "
            "Each candidate gets its own **Conversion strategy** choice (see **Roth Conversion "
            "(Optional)** above for what `fill_to_bracket` vs. `fixed_amount` do), bracket "
            "ceiling/amount, and window.\n"
            "- **`withdrawal_sequencing`** -- same scenario, different **Withdrawal strategy** "
            "choices per candidate (see **Run Simulation** above for what the two options do).\n"
            "- **`claiming_age_grid`** -- same scenario, different Social Security claiming ages "
            "per candidate, one age per household member.\n\n"
            "The chart and table update to whatever the chosen axis produced once you click "
            "**Compare**."
        ),
    ),
]
