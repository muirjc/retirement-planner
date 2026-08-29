# Instructions Page: Requirements

**Status**: Requirements for `/speckit-specify` — feeds a new, small feature (a static "Instructions" page in `apps/streamlit_ui`). Not itself a spec, plan, or implementation.

## 1. Problem

Onboarding a new household onto this tool means sitting down with real financial statements and account balances for both parties in the household (spouses/members) and translating them into the Scenarios form's fields. Nothing in the app currently explains what to gather beforehand or what each field expects — a user hitting the Scenarios page cold has to guess, e.g., whether "Annual spending need" is gross or net, whether the SS annual benefit is at full retirement age or at the entered claiming age, or that account balances are entered as one household-level total per type rather than per person. This is the same class of problem (an unclear field, no cue to the user about what it actually needs) that produced the `reference_tax_year` bug fixed in this project's most recent session — that case was a placeholder value with no warning; this is a field with no explanation.

## 2. Outcome

A new page in `apps/streamlit_ui` that a user reads before (or alongside) filling out the Scenarios form, explaining in plain language what financial information to gather for each party in the household and what every field on that form actually requires.

## 3. Scope

- **Guidance only.** This page explains the existing Scenarios form's fields — it does not itself change the Scenario data model or the form. *(Superseded by `011-per-owner-accounts`: the household-level pooling described below, in force when this requirements doc was written, was later replaced by per-person account attribution — each account is now entered under its owning household member, not pooled into one household-wide total. This page's Accounts guidance reflects that current behavior, not the pooling this bullet originally described.)*
- **Static content, no backend.** The page renders hardcoded text. It calls none of `rp_ui.api_client`'s functions and needs no scenario, simulation, or reference data to render — the first page in this project with zero HTTP dependency on `services/bff`.
- **Out of scope**: any change to `src/retirement_planner`, `services/bff`, or `apps/streamlit_ui/pages/1_Scenarios.py`'s fields themselves.

## 4. Placement and navigation

A new page file, `apps/streamlit_ui/pages/0_Instructions.py`. The `0` prefix sorts it above `1_Scenarios.py` in Streamlit's filename-ordered sidebar (Streamlit's own multi-page convention — pages must sit in `pages/` next to `app.py`, ordered by filename), since it's meant to be read *before* filling out the form, not discovered afterward. `app.py`'s Home page navigation text gets one more line pointing to it.

## 5. Content — one section per field-group on the Scenarios form

Grounded directly in `apps/streamlit_ui/pages/1_Scenarios.py`'s actual fields, so this page can't drift out of sync with what the form asks for:

- **Household** — filing status; per party (member): name/label, current age, Social Security claiming age, and Social Security annual benefit *at that claiming age*. Direction: get the benefit estimate for the specific claiming age entered, not automatically the full-retirement-age figure, from the SSA's own benefit estimator — a mismatched claiming age vs. benefit amount is the single most likely data-entry mistake here.
- **Accounts** — traditional, Roth, and taxable balances, entered **per person**: each party's own balance goes under their own row for each account type — never combined with a spouse's balance, since Required Minimum Distributions are computed per person, from that person's own age and own balance (`011-per-owner-accounts`).
- **Spending** — annual spending need, in **today's dollars** (real, not inflated forward), and gross of taxes (the engine computes taxes; don't net them out beforehand).
- **State** — state of residence for tax purposes. Point to the form's own dropdown for the current supported list rather than hardcoding state codes here, so this page never goes stale when a new state is added.
- **Market assumptions** — equity/bond allocation and return assumptions are the user's own forward-looking planning inputs, not historical fact or something the tool derives. Give a defensible starting point (e.g., a 60/40 allocation with conservative real-return assumptions) framed as an example, not as *the* right answer.
- **Simulation settings** — what `n_paths`, `seed`, and `plan_to_age` each control, in plain language: more paths trade speed for a smoother probability estimate; the seed makes a run reproducible; plan-to-age is the horizon the simulation runs to, not a life-expectancy prediction.
- **Roth conversion (optional)** — when to leave this unchecked vs. fill it in, and what "window" means (the plan-year range the conversion strategy is active).

## 6. Constraints carried over from this project's existing conventions

- No dependency on `retirement_planner` or `rp_bff` — already true for this whole package; this page adds nothing that would change it.
- No new third-party dependency — plain `st.markdown()`/`st.header()`/`st.expander()`, nothing beyond what `apps/streamlit_ui/pyproject.toml` already declares.
- Every figure or example given is clearly framed as an example or rule of thumb, never presented as an authoritative number the tool computed — consistent with the project's Accuracy Over Cleverness / Auditability principles, even though this page performs no computation of its own.

## 7. Suggested next step

Run `/speckit-specify docs/instructions_page_requirements.md` to produce the next numbered feature (`009`), continuing this project's established spec → plan → tasks → implement workflow.
