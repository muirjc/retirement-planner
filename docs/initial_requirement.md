# Retirement Planning Tool — Initial Specification

**Status:** Draft v0.1 — for review and iteration
**Date:** August 27, 2026
**Origin:** Extends `retirement_monte_carlo.py` and `retirement_multistate_comparison.py` prototypes into a specification for a maintained, extensible tool.

---

## 1. Purpose

Build a single-user retirement planning tool that answers three linked questions on an ongoing basis, as inputs and assumptions change over time:

1. **Longevity**: Given a spending need, account mix, and market uncertainty, how confident should I be that the money lasts to a target age?
2. **Tax optimization**: Given a specific state and income profile, what's the tax-efficient sequence of withdrawals and Roth conversions?
3. **Location comparison**: Holding market risk constant, how much does state of residence move the outcome?

This is not a one-off analysis — it's infrastructure meant to be rerun as account balances, tax law, and personal timelines change, consistent with how the working state-comparison document has already been maintained iteratively across sessions.

### 1.1 Non-goals (explicitly out of scope for v1)

- Multi-user / multi-household support (not a SaaS product; single-household tool)
- Investment advice or trade execution
- Legal or tax filing functionality
- Real-time account aggregation (data entry is manual/config-driven, not linked to brokerages)
- Estate planning / inheritance tax optimization beyond flagging exposure (already tracked qualitatively in the state comparison doc)

---

## 2. Reference Use Case

The tool should be validated against a concrete profile before being considered general-purpose:

- Married filing jointly household
- Income sources: Traditional IRA RMDs, Roth IRA withdrawals, Social Security (two claiming ages)
- A defined Roth conversion bridge window (e.g., 2028–2034) ending the year before RMDs begin
- Candidate state set: FL, GA, NC, SC, TN, MS, PA, NH, DE — each with materially different tax mechanics (zero income tax, exclusion-based, full-exemption, graduated-bracket)
- Hurricane/flood exposure and Medigap pricing structure as decision factors *alongside* the financial model, not inside it (see §9, integration boundary)

This profile is the acceptance-test baseline: any refactor or new feature must reproduce the same directional conclusions the prototype scripts already produced for it.

---

## 3. Functional Requirements

### 3.1 Input / Configuration Layer

| Requirement | Detail |
|---|---|
| Structured config | All person, account, and assumption inputs defined in one place (dataclass/schema), not scattered across code |
| Versioned scenarios | Support saving named scenarios (e.g., "base case," "early retirement," "high spending") so results are comparable across runs, not just the last-edited config |
| Validation on load | Reject or flag configs with impossible values (negative balances, claim age outside 62–70, spending exceeding total assets, etc.) before simulation runs |
| Separation of person data from engine code | Config should be data (YAML/JSON/CSV), not hardcoded in the simulation module — current prototypes hardcode via `PlanInputs` dataclass edits, which is fine for single-user iteration but should not require code edits to change a number |

### 3.2 Tax Engine

| Requirement | Detail |
|---|---|
| Federal MFJ bracket calculation | Progressive bracket math (already implemented); needs to move from fixed-in-real-terms brackets to an explicit, documented inflation-indexing assumption per bracket edge |
| Pluggable state tax modules | Each state implemented as an independent module conforming to a common interface (`compute_state_tax(income_components, filer_ages, params) -> float`), not a single dict of blended rates. Current prototype's `generic_state_tax()` blended-rate approximation for graduated states (SC, DE) should be replaced with real bracket-by-bracket logic before any state comparison is decision-grade |
| Social Security taxability | Federal provisional-income rules (0%/50%/85% thresholds) — currently approximated as a flat 85% inclusion; needs the actual threshold logic |
| IRMAA modeling | Not in current prototypes. Required for any household where MAGI could cross Medicare premium surcharge tiers — directly relevant given the existing Medicare/HSA coordination work in the state comparison doc |
| NIIT (Net Investment Income Tax) | Not in current prototypes. 3.8% surcharge above MFJ thresholds on investment income — relevant given taxable account balance and Roth conversion income stacking |
| State exclusion/bracket source-of-truth | Every hardcoded threshold (GA $65k/person, SC $15k/person, DE $12,500/person, etc.) must carry a citation and last-verified date, mirroring the checkbox-flagged open items already in the state comparison document — the tool should surface "needs verification" flags in output, not silently treat placeholder figures as authoritative |
| Legislative sunset handling | GA, NC, MS rates are scheduled to keep changing through 2028–2029 per the working doc. Tax modules should accept a schedule (year → rate/threshold) rather than a single static value |

### 3.3 Retirement Account Mechanics

| Requirement | Detail |
|---|---|
| RMD calculation | IRS Uniform Lifetime Table lookup (implemented); needs Joint Life Table branch for the case where the spouse is the sole beneficiary and >10 years younger |
| Roth conversion bridge | Fill-to-bracket-ceiling logic (implemented); should become configurable strategy, not a single hardcoded rule — see §3.4 |
| Withdrawal sequencing | Current fixed order (RMD → taxable → traditional → Roth) should be a swappable strategy, since sequencing order materially affects both tax drag and longevity |
| HSA coordination | Not yet modeled. Given the documented 6-month Medicare backdating contribution trap and the younger-spouse-retains-eligibility finding, HSA contribution/eligibility timing should be a modeled income-side constraint, not left to manual tracking |

### 3.4 Strategy / Optimization Layer

This is new relative to the prototypes, which run one fixed strategy per simulation.

| Requirement | Detail |
|---|---|
| Roth conversion strategy comparison | Run multiple conversion strategies (fill-to-10%-bracket, fill-to-22%-bracket, fixed dollar amount, no conversion) against the same market draws and compare success rates — the current prototype hardcodes one bracket ceiling |
| Withdrawal order comparison | Same paired-simulation approach already used for state comparison, applied to withdrawal sequencing choices |
| Social Security claiming age sensitivity | Currently fixed inputs; should support a claiming-age grid (62–70 for each spouse) run through the same Monte Carlo engine |

### 3.5 Simulation Engine

| Requirement | Detail |
|---|---|
| Monte Carlo core | Multivariate normal return draws for equity/bond blend (implemented) |
| Paired-draw comparison methodology | Already implemented for state comparison (identical random draws reused across scenarios) — this pattern should be the standard for *any* comparative run (states, strategies, claiming ages), not reimplemented ad hoc each time |
| Historical bootstrap option | Add an alternative return-generation mode that resamples actual historical annual return sequences (e.g., 1926–present) rather than only parametric normal draws, since fat tails and real sequencing (not just mean/variance) matter for sequence-of-returns risk |
| Explicit sequence-of-returns stress test | Already implemented as a fixed "bad first 5 years" scenario; should become parameterized (configurable shock magnitude and duration, applied at configurable points in retirement, not just year 1) |
| Longevity/mortality modeling | Not yet modeled — currently a fixed `plan_to_age`. Consider optional actuarial survival curves so "success rate" can be expressed as "probability of running out while at least one spouse is alive" rather than a fixed horizon |

### 3.6 Reporting / Output

| Requirement | Detail |
|---|---|
| Fan chart (percentile bands over time) | Implemented |
| Multi-scenario overlay chart | Implemented for states; should generalize to any comparison axis (strategy, claiming age, state) |
| Summary statistics table | Implemented (success rate, median/percentile ending balance, depletion age); should add median lifetime taxes paid per scenario, since tax efficiency and longevity are both decision inputs |
| CSV/data export | Implemented; needed for feeding results into the existing markdown working document workflow (pipe-table conventions) rather than requiring manual retyping |
| Verification flags surfaced in output | Any hardcoded figure not yet confirmed against a primary source should visibly propagate into chart/report output (as in the current red-bar convention for GA/SC/DE), not just live in code comments |

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Accuracy over cleverness** | Where a simplification is made (blended state rates, fixed real-terms brackets, no IRMAA/NIIT), it must be explicitly documented in-code and in output, not silently absorbed. Matches the existing working document's discipline of flagging unverified figures rather than presenting them as settled |
| **Reproducibility** | Same config + same random seed → identical results. Already true of the prototypes via `np.random.default_rng(seed)`; must be preserved through any refactor |
| **Auditability** | Every tax rate, exclusion amount, or bracket threshold should be traceable to a source and date, following the citation discipline already used in the state comparison document's Sources section |
| **Extensibility** | Adding a 10th state or a new withdrawal strategy should not require touching the simulation core — enforced via the module-interface pattern in §3.2 and §3.4 |
| **Performance** | 3,000–5,000 simulations × 9 states currently completes in well under a minute on a laptop; this should remain true as complexity grows — historical bootstrap and joint-life RMD tables should not meaningfully regress runtime |
| **No dependency on network access at runtime** | Simulation should run entirely offline once configured; any rate-lookup or verification step is a separate, explicit refresh action, not a runtime dependency |

---

## 5. Architecture Sketch

```
config/
  scenarios/*.yaml          # named, versioned input sets
  state_tax_rules/*.py      # one module per state, common interface
  federal_tax_rules.py

engine/
  rmd.py                    # Uniform Lifetime + Joint Life tables
  social_security.py        # provisional-income taxability rules
  roth_conversion.py        # strategy interface + implementations
  withdrawal_sequencing.py  # strategy interface + implementations
  returns.py                # parametric + historical-bootstrap generators
  simulate.py               # single-path simulation (state/strategy agnostic)
  monte_carlo.py            # paired-draw driver, any comparison axis

reporting/
  charts.py                 # fan chart, overlay chart, bar chart
  tables.py                 # summary stats, CSV export
  verification_flags.py     # propagates "needs source check" into output

cli.py / notebook interface # entry point, matches existing Python-first workflow
```

This is a refactor of the current two-script prototype into separated concerns, not a rewrite — `simulate_one_path()` and `run_multistate_monte_carlo()` from the existing code map directly onto `engine/simulate.py` and `engine/monte_carlo.py`.

---

## 6. Data Model (Sketch)

```yaml
scenario_name: "base_case_2026"
household:
  filing_status: MFJ
  members:
    - name: you
      current_age: 60
      ss_claim_age: 67
      ss_annual_benefit: 32000
    - name: spouse
      current_age: 58
      ss_claim_age: 67
      ss_annual_benefit: 24000
accounts:
  traditional_ira: 1500000
  roth_ira: 400000
  taxable: 200000
spending:
  annual_need_real: 110000
roth_conversion:
  strategy: fill_to_bracket
  bracket_ceiling: 206700
  window: [2028, 2034]
state: GA
market_assumptions:
  equity_allocation: 0.60
  equity_return_mean_real: 0.065
  equity_return_std_real: 0.17
  bond_allocation: 0.40
  bond_return_mean_real: 0.015
  bond_return_std_real: 0.06
  correlation: -0.10
simulation:
  n_paths: 5000
  seed: 42
  plan_to_age: 95
```

---

## 7. Validation Plan

- [ ] Reproduce current prototype outputs exactly from the refactored engine (regression test against `portfolio_percentiles_by_age.csv` and `multistate_comparison_summary.csv` already generated)
- [ ] Unit tests for RMD divisor table against IRS Pub. 590-B values
- [ ] Unit tests for federal bracket math against published 2026 MFJ thresholds
- [ ] Each state tax module tested against at least one hand-calculated example income scenario
- [ ] Cross-check GA HB 463 exclusion amount ($65,000 vs. $70,000/person — open item already flagged in working doc) before GA module is marked verified
- [ ] Cross-check SC phase-in schedule and DE exclusion/rate before those modules are marked verified

---

## 8. Phased Delivery

| Phase | Scope |
|---|---|
| **Phase 1 (current)** | Two standalone scripts: single-state Monte Carlo, multi-state comparison. Hardcoded config, blended-rate tax approximations. *(Complete)* |
| **Phase 2** | Config externalized to YAML; state tax modules split out with real bracket logic (not blended rates) for SC and DE; Social Security provisional-income rules implemented; regression tests against Phase 1 output |
| **Phase 3** | Strategy layer: Roth conversion strategy comparison, withdrawal sequencing comparison, Social Security claiming-age grid — all via the paired-draw comparison pattern |
| **Phase 4** | IRMAA and NIIT modeling; historical-bootstrap return option; optional mortality-adjusted success metric |
| **Phase 5** | HSA contribution/eligibility timing as a modeled constraint, integrating the Medicare enrollment mechanics already documented; verification-flag propagation into all report outputs |

---

## 9. Integration Boundary with the Working Document

The tool produces financial/tax outcomes (success rate, ending balance, tax paid). It does **not** attempt to model hurricane/flood exposure, Medigap pricing structure, or healthcare access rankings — those remain qualitative factors tracked in `retirement-state-comparison.md`. The intended workflow is:

1. Tool narrows/ranks states or strategies on financial grounds
2. Working document's non-financial factors (insurance cost reality, issue-age Medigap protection, medical care access) are weighed alongside the tool's output, not inside it
3. Any dollar figures the tool needs from the non-financial side (e.g., an actual homeowners insurance quote for a specific inland town) are manual inputs into the config, not something the tool derives independently

This keeps the simulation engine's scope bounded and prevents it from silently absorbing judgment calls that belong in the narrative document.

---

## 10. Open Questions

- [ ] Should scenario configs live in the same project/directory as `retirement-state-comparison.md`, or in a separate tool-specific repo?
- [ ] Historical bootstrap data source — which return series (S&P 500 total return, Aggregate Bond index) and what date range?
- [ ] Is mortality-adjusted success probability actually wanted, or does a fixed planning horizon (age 95) remain the preferred framing for decision-making?
- [ ] Priority ordering of Phase 2–5 items — the IRMAA/NIIT gap (Phase 4) vs. real bracket math for SC/DE (Phase 2) are both "known simplifications currently overstating precision"; which matters more for the near-term GA-vs-others decision?
