# Business Requirements Document: Retirement Planner

**Status**: Living document — reflects the codebase as of `specs/001`–`023`
**Last reviewed against**: `023-probabilistic-death-draws` (rp-vgv)

> **Keeping this document current**: This BRD is derived from, and must
> stay consistent with, the actual code — every regulation and formula
> named below links back to the module that implements it. Any feature
> that adds a new tax rule, a new regulated figure, or a new piece of
> financial math **must** update the relevant section here in the same
> change, the same way it updates `specs/NNN-*/spec.md`. Verification
> status (§5, §7) in particular goes stale the moment a `SourcedFigure`
> flips `verified` — before trusting §5's table, grep for `verified=`
> across `src/retirement_planner/` and confirm it still matches.

---

## 1. Purpose

Retirement Planner is a single-user financial planning tool that answers
three linked business questions on an ongoing basis, as account balances,
tax law, and personal circumstances change:

1. **Longevity** — given a spending need, account mix, and market
   uncertainty, how confident should the household be that its money
   lasts to a target age?
2. **Tax optimization** — given a specific state of residence and income
   profile, what is the tax-efficient sequence of withdrawals and Roth
   conversions?
3. **Location comparison** — holding market risk constant, how much does
   state of residence move the outcome?

It exists to replace ad hoc spreadsheet/prototype modeling
(`retirement_monte_carlo.py`, `retirement_multistate_comparison.py` — the
two scripts `docs/initial_requirement.md` names as this project's origin)
with a maintained, tested, re-runnable engine, so a household can revisit
the same questions confidently as inputs change, instead of re-deriving
the analysis from scratch each time.

## 2. Business Scope

### 2.1 In scope

- Federal income tax (progressive brackets, Social Security taxability,
  the Net Investment Income Tax surtax, Medicare IRMAA surcharges)
- Three state income tax regimes today (South Carolina, Delaware,
  Florida), via a pluggable per-state module so more states are additive,
  not a rewrite
- Traditional/Roth/taxable account withdrawal mechanics, including
  Required Minimum Distributions (RMDs) for both a living account owner
  and an inherited account under SECURE Act/SECURE 2.0 rules
- Roth conversion strategy comparison (bracket-fill vs. fixed-dollar)
- Withdrawal-order strategy comparison
- Social Security claiming-age sensitivity (a full 62–70 grid per spouse) —
  the grid varies the actual benefit *amount* paid at each candidate age
  (the standard early-reduction/delayed-retirement-credit adjustment,
  §6.2a), not just when payments start
- Pension, annuity, and phased-retirement earned-income streams —
  per-member, fixed or COLA-adjusted fixed income, feeding the same
  ordinary-income pipeline account withdrawals and Social Security already
  do (§6.2d)
- HSA contribution eligibility and annual limit tracking
- Monte Carlo simulation (parametric and historical-bootstrap return
  generation, sequence-of-returns stress overlay, optional
  survival-adjusted success scoring)
- Deterministic (single-path) and simulated (Monte Carlo) comparison
  across any one axis — state, withdrawal strategy, Roth conversion
  strategy, or Social Security claiming age — holding every other input,
  including the random market draws themselves, identical across
  candidates ("paired-draw" methodology, §6.7)
- Reporting: fan charts, comparison overlays, summary statistics
  (including median lifetime tax paid), CSV export, and an explicit
  per-figure "needs verification" indicator in every output

### 2.2 Explicit non-goals

Per `docs/initial_requirement.md` §1.1, unchanged since the project's
first draft:

- Multi-user or SaaS support — this is a single-household tool
- Investment advice or trade execution
- Tax return preparation or filing
- Real-time account aggregation (all data entry is manual/config-driven,
  never linked to a brokerage or bank)
- Estate-planning or inheritance-tax optimization beyond what's needed to
  compute an inherited account's own RMD/depletion schedule
- Qualitative, non-financial decision factors — hurricane/flood exposure,
  Medigap pricing structure, healthcare access rankings. These remain
  tracked in a separate narrative document and are deliberately kept out
  of the simulation engine (constitution's "Scope boundary with the
  working document"); a dollar figure this tool needs from that side
  (e.g., an actual insurance quote) is a manual scenario input, never
  something the tool derives on its own.
- **Healthcare premium dollar costs — a distinct case from the
  qualitative factors above, called out explicitly (rp-1pp)**: baseline
  Medicare Part B/D premiums (age 65+) and pre-Medicare ACA marketplace
  premiums/subsidies (the multi-year bridge between an early retirement —
  the reference use case starts household members at 58-60 — and Medicare
  eligibility at 65) are real, load-bearing financial-plan inputs, not
  qualitative judgment calls. Neither is modeled by this engine (§6.4)
  — a household is expected to estimate its own baseline Medicare and/or
  ACA bridge premiums and fold them into `annual_need_real`, the same way
  it would fold in any other recurring expense this tool doesn't itemize
  on its own.

### 2.3 Reference use case

The tool's acceptance baseline (`docs/initial_requirement.md` §2): a
married-filing-jointly household with Traditional IRA, Roth IRA, and
Social Security income (two independent claiming ages), a defined Roth
conversion bridge window, evaluated across a candidate set of states with
materially different tax mechanics (zero-income-tax, exclusion-based,
graduated-bracket, flat-rate). Only 4 of that original 9-state candidate set (South
Carolina, Delaware, Florida, North Carolina) have real tax modules today — the rest
(Georgia, Tennessee, Mississippi, Pennsylvania, New
Hampshire) are named, scoped follow-on work against the same
`compute_state_tax()` interface, not a redesign.

## 3. Primary Users & Usage Pattern

One household, used directly or through an advisor acting on the
household's behalf. The intended pattern is iterative: build a scenario
once (YAML config), re-run it as inputs change (a new account balance, a
new state under consideration, a legislative change), and compare
candidates side by side. It is not a single-shot report generator.

## 4. Business Value

- Replaces a blended-rate, "close enough" approximation of state and
  federal tax with genuine bracket-by-bracket math, so a state-comparison
  or Roth-conversion decision isn't distorted by an approximation error
  the household can't see.
- Makes every externally-sourced number (a bracket edge, an exclusion
  amount, an RMD divisor) individually traceable to a citation and a
  verification status, so the household knows exactly which parts of an
  answer are settled fact and which are still provisional (§5, §7).
- Turns a state-of-residence or withdrawal-sequencing decision from a
  one-off manual spreadsheet exercise into a re-runnable, reproducible
  comparison — same inputs and same random seed always produce the same
  answer (§8).

## 5. Regulatory & Tax Coverage

Every rate, threshold, or table below is implemented as a `SourcedFigure`
(`tax/models.py`) — it carries a citation, a `last_verified` date, and a
`verified` boolean, and that status is threaded through every computed
result's `figures_used` list so a report can show, per figure, whether it
is settled or still provisional (constitution Principle III,
Auditability). "Verified" here means a human or agent has actually
cross-checked the figure against the cited primary source — see
`014-figure-verification`'s own `research.md` for the verification
methodology this table's federal rows were most recently produced by.

### 5.1 Federal — verified

| Figure | Regulation | Module |
|---|---|---|
| Federal income tax brackets (MFJ, single) | IRS Rev. Proc. 2025-32, tax year 2026 | `tax/federal.py` |
| Federal standard deduction (MFJ, single), incl. age-65 addition per filer | 26 U.S.C. §63(c), (f); IRS Rev. Proc. 2025-32 §4.14(1), tax year 2026 | `tax/federal.py` |
| Social Security taxability thresholds | 26 U.S.C. §86(c)(1)-(2) (fixed since 1983, not inflation-indexed) | `tax/social_security.py` |
| Net Investment Income Tax (NIIT) rate & thresholds | 26 U.S.C. §1411(a)(1), (b)(1)/(3) (fixed by statute) | `tax/niit.py` |
| Medicare IRMAA surcharge tiers (Parts B & D, combined) | CMS.gov, 2026 IRMAA tables (CMS-8089-N/8090-N/8091-N) | `tax/irmaa.py` |
| HSA contribution limits (self-only, family, 55+ catch-up) | IRS Rev. Proc. 2025-19, tax year 2026 (catch-up fixed by IRC §223(b)(3)) | `mechanics/hsa.py` |
| RMD start age, including the scheduled 2033 73→75 step | 26 U.S.C. §401(a)(9)(C)(v), as amended by SECURE 2.0 Act (Pub. L. 117-328) §107 | `mechanics/rmd.py` |
| Uniform Lifetime Table (RMD divisors, ages 72–120+) | IRS Pub. 590-B (2025), Appendix B, Table III | `mechanics/rmd.py` |
| Single Life Expectancy Table (inherited-account divisors, ages 0–120+) | IRS Pub. 590-B (2025), Appendix B, Table I | `mechanics/inherited_rmd.py` |
| Social Security claiming-age early-reduction/delayed-credit rates | 42 U.S.C. §402(q)/(w); 20 C.F.R. §404.410/§404.313 (fixed by regulation, not annually revised) | `mechanics/social_security_benefit.py` |
| Social Security spousal-benefit early-claiming reduction rate (25/36 of 1%/month first 36 months, 5/12 of 1%/month beyond; no delayed credit) | 42 U.S.C. §402(b)/(c); 20 C.F.R. §404.410 (wife's/husband's-benefit paragraph, fixed by regulation) | `mechanics/social_security_benefit.py` |
| Social Security survivor-benefit rule (higher of the two benefits continues, the lower stops) | 42 U.S.C. §402(e)/(f); 20 C.F.R. §404.335/§404.336 | `mechanics/social_security_benefit.py` |
| Non-COLA'd ("fixed-nominal") income-stream real-dollar erosion rate (2.40%/year) | SSA, *2025 Annual Report of the Boards of Trustees of the OASI and DI Trust Funds*, "Long-Range Economic Assumptions," intermediate assumption, ultimate CPI increase — a planning assumption, not binding law, unlike every other row above | `mechanics/income_streams.py` |
| FICA OASDI rate (6.2%), Medicare/HI rate (1.45%, uncapped), 2026 OASDI wage base ($184,500) | SSA, "2026 Cost-of-Living Adjustment (COLA) Fact Sheet" (ssa.gov/news/en/cola/factsheets/2026.html); cross-checked against SSA's own Contribution and Benefit Base page (ssa.gov/oact/cola/cbb.html) | `tax/fica.py` |
| Additional Medicare Tax rate (0.9%) and thresholds ($200,000 single / $250,000 MFJ, fixed since 2013, not inflation-indexed) | 26 U.S.C. §3101(b)(2); IRS, "Questions and Answers for the Additional Medicare Tax" | `tax/fica.py` |

**Simplification, documented not hidden**: the RMD start-age step above is
modeled as a tax-year cutoff (73 before 2033, 75 from 2033 on), not the
statute's actual birth-year cohort rule (age 73 for those born 1951–1959,
age 75 for 1960+). Full cohort modeling would require threading the
account owner's birth year through `compute_rmd()`'s locked signature — a
larger, separately-scoped change (`014-figure-verification`, research.md
§3).

### 5.2 Federal — real math, "real-dollar" bracket/tier convention

Federal brackets, the standard deduction, and IRMAA tiers are pinned to
one specific, cited tax year (2026) and held flat across every documented
year rather than re-indexed annually — the same "real (inflation-adjusted)
dollars, no further indexing engine" convention `tax/federal.py`'s own
docstring establishes and `tax/irmaa.py` explicitly reuses. This is an
explicit, documented assumption (constitution Principle I), not silently
absorbed imprecision: a multi-decade projection uses today's real-dollar
bracket edges (and standard deduction) throughout, rather than projecting
a nominal-dollar inflation schedule this tool has no separate model for.

### 5.3 Federal — not modeled

- **Joint Life and Last Survivor Table** (IRS Pub. 590-B, Table II) —
  implemented (`mechanics/rmd.py`, used when a spouse is the sole named
  beneficiary and more than 10 years younger) but ships with only a
  handful of age pairs and `verified=False`; extending it to the full
  published table is named follow-on work, out of `014`'s scope.
- **Full SECURE 2.0 birth-year RMD cohorts** — see §5.1's simplification
  note.
- Trust/entity inherited-account beneficiaries — blocked by a validation
  flag before reaching any computation (`013-inherited-ira-edge-cases`),
  not silently mis-computed.
- **Social Security spousal/survivor benefits — remaining gaps
  (rp-52n, rp-g8y)**: the spousal-benefit floor (§6.2b) is modeled and
  applied in every married-filing-jointly projection. The
  survivor-benefit calculation and its mid-horizon projection wiring
  (§6.2b/§6.2c) — filing status switching to single, Social Security
  income switching to the survivor amount, and spending need reduced by
  a household-configured percentage, all from the year after a
  configured death forward — are now modeled for deterministic and
  strategy-comparison projections. Monte Carlo simulation's default
  behavior still applies the same household-configured death year to
  every path (§6.2c); an opt-in, core-library-only per-path probabilistic
  death draw now exists (§6.8, rp-vgv) but isn't yet exposed through the
  BFF or Streamlit UI. Still not modeled: Qualifying Surviving Spouse
  status or a joint return specifically for
  the year of death (this engine switches straight from
  married-filing-jointly through the death year to single the year
  after, which may overstate the survivor's near-term tax burden
  relative to real law); remarriage; a detailed post-death budget
  re-plan beyond the single configured spending percentage; and a second
  (the survivor's own, later) configured death ending the projection.
  Also not modeled: the Social Security family maximum benefit (the
  aggregate cap on total benefits payable on one worker's record — this
  tool's households of at most two members are the case that least often
  binds it), "deemed filing" mechanics (a household's own-benefit and
  spousal-benefit filings are treated as one combined application in
  most post-2015 cases, not a genuine free choice modeled here), and the
  widow(er)'s-own early-claiming reduction and statutory "widow's limit"
  cap on the survivor-benefit calculation itself.
- **Social Security earnings test** — a member who claims while still
  working before FRA is not subject to the benefit withholding the
  earnings test would impose; the tool assumes full, unwithheld payment
  from the configured claiming age on.
- **Itemized deductions and the temporary OBBBA senior bonus deduction**
  (an additional $6,000/qualifying taxpayer for age 65+, phased out above
  $75k/$150k MAGI, tax years 2025-2028) — every household is modeled as
  taking the standard deduction (§5.1); a household that would itemize, or
  that qualifies for the senior bonus deduction, has its federal tax
  overstated relative to that household's actual liability.
- **Self-employment (SECA) tax on `earned_income` income streams**
  (rp-elp, §6.2e) — employee-side FICA (Social Security + Medicare +
  Additional Medicare Tax) on `earned_income` streams is now modeled
  (§6.2e), closing most of this gap as originally described (rp-pid,
  §6.2d). What remains unmodeled: the 15.3% combined self-employment rate
  a 1099/sole-proprietor household member's earned income would actually
  owe — a household whose phased-retirement earnings are genuinely
  self-employment income, rather than W-2 wages, will still see its true
  payroll-tax cost understated. Named follow-on work, not silently
  absorbed.

### 5.4 State — South Carolina, Delaware, Florida, North Carolina

| State | Structure | Verification status |
|---|---|---|
| Florida (FL) | No state income tax — always returns $0, consults no figures | Trivially exact by definition; no citation needed (`tax/state/fl.py`) |
| South Carolina (SC) | Graduated brackets + age-65 retirement-income exclusion | **Unverified placeholder** — round numbers in the right order of magnitude, not the real SC Code figures (`tax/state/sc.py`) |
| Delaware (DE) | Graduated brackets + age-60 retirement-income exclusion | **Unverified placeholder** — same status as SC (`tax/state/de.py`) |
| North Carolina (NC) | Flat rate (4.25% tax year 2025, 3.99% 2026 onward), no age-based exclusion | **Verified** — confirmed against NCDOR's Tax Rate Schedules and N.C. Gen. Stat. §105-153.7 as amended by S.L. 2023-134 (`tax/state/nc.py`, `024-nc-state-tax`). Does **not** model North Carolina's Bailey-settlement retirement-income exclusion (pre-8/12/1989-vested government/military pension income only) — that mechanism keys off income source and pension vesting date, neither of which `IncomeComponents` carries; see `specs/024-nc-state-tax/spec.md` Assumptions. |

South Carolina and Delaware were **not** in scope for `014-figure-verification` — that effort covered only the 8 federal figures a specific run flagged. Verifying SC/DE against South Carolina and Delaware statutory text is tracked as separate, not-yet-scheduled follow-on work. North Carolina's flat rate was verified directly as part of `024-nc-state-tax`, not inherited as placeholder debt.

### 5.5 Inherited retirement accounts (SECURE Act / SECURE 2.0)

Covers the 10-year rule and its exceptions, per `mechanics/inherited_rmd.py`
(`012-inherited-ira-rmd`, extended by `013-inherited-ira-edge-cases`):

- **Non-eligible designated beneficiary** (the common case since the
  original SECURE Act): full account depletion by the 10th calendar year
  after the owner's death; an annual RMD is additionally required for
  years 1–9 if the original owner had already reached their own Required
  Beginning Date (RBD) before death, using the longer of the
  beneficiary's own life expectancy or the original owner's remaining
  life expectancy (rp-kn5) — not just the owner's, as originally shipped;
  see the EDB bullet below for the same "longer of" mechanics.
- **Owner died before their RBD, or the account is a Roth**: no annual
  RMD during the 10-year window at all — full depletion by year 10 is the
  only requirement.
- **Eligible designated beneficiary (EDB)** — a spouse, a minor child (until
  age 21, at which point the 10-year rule takes over), someone not more
  than 10 years younger than the owner, or a disabled/chronically ill
  individual — takes an annual "stretch" distribution instead of the
  10-year rule, using the longer of the beneficiary's own life expectancy
  or the original owner's remaining life expectancy for a post-RBD case;
  a spouse beneficiary's divisor is recalculated fresh every year rather
  than decremented by one, and a spouse can delay starting until the year
  the original owner would have reached their own RBD.
- **Trust or entity beneficiary**: not modeled — caught by a blocking
  validation flag rather than silently computed with the wrong rule.

## 6. Financial Methodology (the math)

### 6.1 Progressive federal/state bracket tax

Genuine bracket-by-bracket math, not a blended average rate:
`tax += min(taxable_income, bracket_upper) - bracket_lower) * bracket_rate`,
accumulated bracket by bracket (`tax/bracket_math.py`'s
`apply_progressive_brackets()`, shared by federal and every graduated-bracket
state module).

### 6.2 Social Security taxability (the "provisional income" test)

Per 26 U.S.C. §86: `provisional_income = ordinary_income + 0.5 × gross SS
benefit`. Below the first threshold, 0% of the benefit is taxable;
between the two thresholds, up to 50% is taxable
(`min(0.5 × benefit, 0.5 × (provisional_income − threshold_1))`); above
the second threshold, up to 85% is taxable, computed as the smaller of
`0.85 × benefit` and `0.85 × (provisional_income − threshold_2) +
(the 50%-tier amount already accrued up to threshold_2)`.

### 6.2a Social Security claiming-age benefit adjustment

A household member's configured Social Security figure is their Primary
Insurance Amount (PIA) — the benefit payable if claimed exactly at their
full retirement age (FRA), which is itself now a configurable per-member
input (defaulting to that member's own claiming age when not set, so a
scenario predating this feature keeps producing exactly its prior output
unless it explicitly opts in with a real PIA/FRA pair). The benefit
actually paid at a chosen claiming age is derived from the PIA and FRA
together, per 42 U.S.C. §402(q)/(w) and 20 C.F.R. §404.410/§404.313:

- Claiming before FRA: reduced by 5/9 of 1% per month for each of the
  first 36 months claimed early, plus 5/12 of 1% per month for any
  additional months beyond that (e.g. claiming at 62 against a 67 FRA is
  60 months early — a 30% reduction, ~70% of PIA).
- Claiming exactly at FRA: paid at 100% of PIA, unadjusted.
- Claiming after FRA, up to age 70: increased by 2/3 of 1% per month (8%
  per year) delayed, with no further credit accruing past age 70 (e.g.
  claiming at 70 against a 67 FRA is a 24% credit, ~124% of PIA).

This is what makes the claiming-age comparison grid (§2.1) show a genuine
early-vs-late trade-off rather than mechanically favoring the earliest
claiming age — before this was modeled, every candidate age in the grid
received the same flat PIA for a different number of years, which
structurally could never show delaying as the better choice even when it
genuinely was.

Explicitly not modeled here: the Social Security earnings test for a
member who claims while still working before FRA — tracked as a known
gap, not silently assumed away. Spousal and survivor benefits are now
modeled — see §6.2b.

### 6.2b Social Security spousal and survivor benefits (rp-52n)

Each member's own claiming-age-adjusted benefit (§6.2a) is no longer the
final word for a married-filing-jointly household — two further SSA
rules now apply:

- **Spousal-benefit floor**: once both members have reached their own
  claiming age, each member's Social Security income is raised to the
  greater of their own claiming-age-adjusted benefit or a spousal amount
  — up to 50% of the *other* member's PIA, adjusted for the claiming
  member's own claiming age relative to their own FRA using the SSA's
  spousal-specific early-claiming reduction rate (25/36 of 1% per month
  for the first 36 months claimed early, 5/12 of 1% per month beyond
  that — a different, larger tier-1 rate than the worker's-own-benefit
  reduction in §6.2a). No delayed-retirement credit ever applies to a
  spousal amount: it is capped at exactly 50% of the other member's PIA
  for claiming at or after FRA, no matter how much later than FRA the
  claiming member actually files. This is wired into every deterministic
  and Monte Carlo projection today (42 U.S.C. §402(b)/(c); 20 C.F.R.
  §404.410).
- **Survivor benefit**: given both members' own currently-claimed
  benefit amounts, the surviving member's ongoing benefit is the higher
  of the two — the lower one stops entirely (42 U.S.C. §402(e)/(f); 20
  C.F.R. §404.335/§404.336). `HouseholdMember` can record a member's
  hypothetical death (`predicted_death_age`, opt-in, `None` by default);
  §6.2c describes how a running projection now actually applies it.

Explicitly not modeled: the Social Security family maximum benefit,
"deemed filing" mechanics, and — on the survivor-benefit calculation
itself — the widow(er)'s-own early-claiming reduction and the statutory
"widow's limit" cap (§5.3) — tracked as known gaps, not silently assumed
away.

### 6.2c Survivor scenario projection wiring (rp-g8y)

For a married-filing-jointly household where one member has
`predicted_death_age` configured, `run_plan_projection()` — the single
per-plan-year loop every deterministic projection, strategy comparison,
and Monte Carlo path already shares — now changes behavior mid-horizon.
The death *tax year* is the first year that member's translated age
reaches `predicted_death_age`; the death year itself, and every year
before it, is unaffected (mirroring real income-tax law's allowance of a
joint return for the year a spouse actually dies, without this engine
modeling Qualifying Surviving Spouse status for the years after). From
the following tax year through the end of the horizon:

- **Filing status** switches to `single` for every computation that
  consumes it (federal tax, state tax, IRMAA, NIIT, and the Roth
  conversion bracket-ceiling logic).
- **Social Security income** switches from the sum of both members'
  benefits to the survivor-benefit amount (§6.2b) — computed from each
  member's own already-claiming-age-adjusted (and, if applicable,
  spousal-floor-adjusted) benefit for that year, so the number used is
  whatever was actually being paid immediately before the death, not a
  synthetic recomputation.
- **Spending need** is multiplied by `(1 - Household.survivor_spending_reduction_pct)`
  — a new, opt-in household-level field (fraction 0.0–1.0, default 0.0 —
  a true no-op, so a household that omits it keeps its full pre-death
  spending). This is a single flat assumption, not a detailed re-planned
  budget.

Each plan year's *effective* filing status and spending need (not just
the household's static configured values) are retained on that year's
own result, so a report or chart can show exactly when the switch
occurred — this is what makes the "widow's tax penalty" (narrower single
brackets, lower Social Security-taxability/NIIT/IRMAA thresholds, one
Social Security check instead of two, near-full household expenses)
visible in this tool's output for the first time.

A household where no member has `predicted_death_age` configured — the
overwhelming majority of scenarios — is completely unaffected; every
year's effective filing status and spending need simply equal the
household's configured values, unchanged.

**Not modeled** (see §5.3 for the full list): Qualifying Surviving Spouse
status; remarriage; a detailed post-death budget re-plan; and a second
(the survivor's own, later) configured death ending the projection early.
Monte Carlo simulation's *default* behavior still matches this section
exactly — every path uses the same deterministic, household-configured
death year a plain projection would — but an opt-in, core-library-only
capability now lets a caller instead give each path its own probabilistic
death year (§6.8) drawn from an actuarial curve, reusing this section's
own filing-status/Social-Security/spending-reduction switch unchanged for
whichever death year that specific path drew.

### 6.2d Pension, annuity & phased-retirement income streams (rp-pid)

Beyond Social Security and account withdrawals, a household member can now
be configured with zero or more generic fixed **income streams** —
pensions, annuity payouts, or phased-retirement earned income — each with
a label, a type (`pension`/`annuity`/`earned_income`, informational only),
a start age, an optional end age (inclusive; omitted means the stream
pays for the rest of the plan, like Social Security once claimed), an
annual amount (today's dollars), and an inflation-adjustment mode.

**Tax treatment**: unlike Social Security, a stream's full amount is
included in ordinary taxable income — none of it is excluded via the
provisional-income test (§6.2). It is folded into the same
`ordinary_income_established` total a traditional withdrawal already
contributes, *before* Roth-conversion bracket-fill sizing runs, so a
configured pension correctly reduces that year's remaining
bracket-fill headroom the same way a traditional withdrawal does.

**COLA-adjusted vs. fixed-nominal, in a real-dollar engine**: this tool
already works entirely in real (inflation-adjusted) dollars, with no
separate nominal-dollar projection (§5.2) — so a cost-of-living-adjusted
income source, in that convention, is simply held flat at its configured
amount, the same treatment Social Security's own PIA already gets. A
*non*-COLA'd ("fixed-nominal") stream is the opposite: its real
purchasing power genuinely erodes every year, so it is discounted against
a new, explicitly cited inflation-rate figure — the Social Security
Trustees Report's own intermediate-assumption ultimate CPI rate (2.40%),
compounded from the scenario's start year (not from the stream's own
start age, so a not-yet-started stream still loses the same real value
while waiting). This is this tool's first inflation-rate figure, and the
one figure in this feature that is a planning assumption rather than
settled law (§5.1's verified-figures table flags it accordingly).

**Cash-flow treatment**: mirrors Social Security exactly — a configured
stream does **not** reduce the amount withdrawn from accounts to meet
`annual_need_real`; it is additional taxable income layered on top, the
same way Social Security already is. This keeps the two income sources
internally consistent rather than introducing a different cash-flow rule
for one and not the other.

**The `earned_income` double-counting trap (rp-uaf)**: this rule is a much
easier trap to fall into for `earned_income` than for `pension`/`annuity`.
A household typically configures Social Security and a pension consistently
from the start (both are "extra income on top"), but a scenario author
modeling "my spouse keeps their $60k salary for 3 more years" naturally
thinks of that salary as *already covering* part of the household's living
costs — and has to remember to manually reduce `annual_need_real` by
whatever portion of spending that salary already funds. Nothing in the
engine validates, warns, or otherwise catches a scenario where a large
`annual_need_real` and a large `earned_income` stream coexist without that
manual netting: the full spending need is withdrawn from accounts *and*
the salary is taxed on top, with no offsetting cash inflow anywhere. This
is not a bug — `annual_need_real`'s own definition ("the net amount that
must come from savings") is correct and, per the paragraph above,
consistent with how Social Security is already treated — but it is a
usability gap. Decision: fixed as documentation/UX only (rp-uaf), not an
engine change — see the `earned_income`-specific warning in the Type
field's help text and the Spending field's help text on the Streamlit
Scenarios page (`apps/streamlit_ui/pages/1_Scenarios.py`), and the
Household/Spending sections of the Instructions page
(`apps/streamlit_ui/src/rp_ui/instructions_content.py`). A soft validation
warning was considered and rejected: the engine has no way to tell whether
an author already netted a stream's contribution out of `annual_need_real`,
so a rule that fires whenever a nonzero `earned_income` stream is present
would just repeat the help text on every such scenario rather than
detecting an actual problem.

Streams round-trip through the scenario YAML and the BFF API, and the
Streamlit Scenarios page now offers real per-member add/edit/remove
widgets for them (`rp-5cq`) — not just silent preservation of an
already-configured stream on save, the gap this section originally
flagged.

**Not modeled**: payroll/self-employment tax on `earned_income` streams
(§5.3); any automatic survivor/joint-and-survivor continuation of a
pension or annuity after the owning member's death (model a second,
independent stream instead); regulatory payout caps (e.g. IRC §415(b)).

### 6.2e FICA payroll tax on earned-income streams (rp-elp)

`earned_income` income streams (§6.2d) now carry employee-side FICA
payroll tax, closing the gap that feature explicitly left open:

- **Social Security (OASDI)**: 6.2% of each household member's own
  combined `earned_income` amount for the year, capped at the annual
  Social Security wage base ($184,500 for 2026) — the cap applies
  per worker, so a household with two earning spouses caps each
  spouse's own OASDI independently.
- **Medicare (HI)**: 1.45% of each member's own `earned_income`, with no
  cap.
- **Additional Medicare Tax**: a further 0.9%, computed once per
  household (not per member) on the household's *combined* `earned_income`
  above a filing-status threshold ($200,000 single / $250,000 married
  filing jointly) — matching how this tax actually reconciles on IRS Form
  8959 for a married couple, not a per-spouse check against a
  single-filer-shaped number.

Every dollar of this tax is funded from the household's own account
balances the same plan year it's owed, exactly like federal/state income
tax, the IRMAA surcharge, NIIT, and the early-withdrawal penalty already
are — it genuinely reduces projected cash flow, not merely appears
alongside it in a report. The wage base is pinned to its 2026 published
value and held flat across every documented year, the same "real dollars,
no further indexing engine" convention federal brackets and the standard
deduction already use (§5.2) — the Additional Medicare Tax's $200k/$250k
thresholds are held flat for a different reason: they are genuinely fixed
by statute (26 U.S.C. §3101(b)(2)) since the tax took effect in 2013, not
merely an engine convention standing in for missing data.

**Not modeled**: self-employment (SECA) tax. This models only the
employee-side W-2 rates above, not the 15.3% combined self-employment
rate a 1099/sole-proprietor household member's `earned_income` would
actually owe — a household whose phased-retirement earnings are genuinely
self-employment income will see this feature understate their true
payroll-tax cost. `pension`/`annuity` streams never incur FICA at all
(they are not wages) — this is the correct treatment, not a gap.

### 6.3 Net Investment Income Tax (NIIT)

`surtax_owed = min(investment_income, magi − threshold) × 0.038`, applied
only once MAGI strictly exceeds the filing-status threshold — the same
"lesser of" bound 26 U.S.C. §1411 itself uses, never the household's full
investment income once any threshold is crossed.

### 6.4 IRMAA surcharge

A tiered lookup: the highest MAGI tier at or below the household's MAGI
determines a flat annual per-person surcharge (`surcharge_owed =
annual_surcharge_per_person × enrolled_member_count`); a tier's lower
bound is inclusive.

**What this covers, and what it doesn't (rp-1pp)**: this is the
income-related *surcharge* only — the incremental amount a
higher-income household pays *above* the standard Medicare Part B/D
premium. This engine does not model the standard baseline premium
itself (the amount every enrollee pays regardless of income), nor any
pre-Medicare ACA marketplace premium or subsidy for the bridge years
before age 65 (§2.2). Both are real dollar costs a household must
estimate on its own and fold into `annual_need_real` — this tool has no
separate line item for either today.

### 6.5 Required Minimum Distributions

`required_amount = traditional_balance ÷ divisor`, where the divisor
comes from the Uniform Lifetime Table (the default) or the Joint Life and
Last Survivor Table (when a spouse is the sole named beneficiary and more
than 10 years younger) looked up by the account owner's current age. An
inherited account uses the Single Life Expectancy Table instead, per the
rules in §5.5.

### 6.6 Roth conversion & withdrawal sequencing

Two Roth conversion strategies ship: fill ordinary income up to a
configured federal bracket ceiling each year, or convert a fixed dollar
amount each year — both aware of how the conversion itself feeds back
into Social Security taxability (26 U.S.C. §86) in the same tax year.
Withdrawal order is modeled as a named, swappable sequence of account
types (e.g., taxable → traditional → Roth) rather than one hardcoded
order, so comparing sequencing strategies means comparing two data
values, not two code paths.

**Roth conversion five-year (conversion-ladder) tracking (rp-886)**: each
conversion a projection actually executes is tracked as its own "lot,"
carrying its own individual five-tax-year seasoning clock (26 U.S.C.
§408A(d)(3)(F); Treas. Reg. §1.408A-6, Q&A-5) — a converted dollar is not
treated as if it had always been a regular contribution (for
early-distribution purposes) until 5 full tax years have elapsed from its
own conversion year, independent of any other conversion's own clock. A
household's pre-existing Roth balance as of a projection's start is
always treated as already-seasoned/fully accessible (this tool has no
input describing that starting balance's own composition or age — a
documented simplification). When a plan year's withdrawal needs to draw
past that pre-existing balance into one or more tracked conversion lots
(drawn oldest-conversion-year-first, matching real IRS Roth distribution
ordering), the amount actually sourced from a lot that hasn't yet cleared
5 years is **flagged** on that plan year's output whenever at least one
household member's translated age is 59 or younger that year (a
conservative, household-level simplification — this engine pools Roth at
the household level, with no per-member ownership, so the check applies
until *every* member has cleared the age condition, erring toward
over-flagging rather than missing a real violation). This flag now feeds
directly into the 10% early-withdrawal penalty described in §6.6a — it is
no longer merely informational.

### 6.6a Early-withdrawal penalty, pre-59.5 (rp-8z0)

A flat 10% additional tax (26 U.S.C. §72(t)(1)) applies each plan year to
the household's combined **taxable early-distribution base**: each
household member's own share (via the same per-owner `traditional_ownership_shares`
attribution §6.5's RMD calculation already uses) of that year's *voluntary*
(non-RMD) Traditional withdrawal, for any member whose translated age is
59 or younger, plus that same year's own unseasoned Roth
conversion-withdrawal amount (§6.6's own conversion-ladder flag, consumed
directly — this feature does not re-derive lot seasoning or re-check
age for it). The two sources are combined into a single reported penalty,
not two separate figures.

Two real statutory exclusions apply automatically, by construction, not
via an explicit check: an RMD-mandated distribution is never included
(the RMD leg is tracked entirely separately from a voluntary withdrawal,
and in any case this tool's RMD start age is never under 73 — always well
past 59½); and an inherited account's own distribution to its beneficiary
is never included, regardless of the beneficiary's own age (a distinct
provision from a Traditional/Roth owner's own early access — this tool
already tracks inherited-account distributions as an entirely separate
stream, per §5.5).

This penalty is included in the amount actually funded each plan year, so
it genuinely reduces a household's projected ending balance, not merely
its reported lifetime cost — the same is now true of the IRMAA/NIIT
amounts described in §6.3/§6.4 (`rp-yqf`: found, during this feature's
own specification, to be reported but not yet actually deducted from
projected balances at the time; fixed as a follow-on correction shortly
after).

### 6.7 Comparison methodology (paired-draw)

Every comparison — across states, withdrawal strategies, Roth conversion
strategies, or Social Security claiming ages — reuses the **same**
random market draws across every candidate being compared, varying only
the one dimension under test. This isolates the effect actually being
measured (e.g., "does South Carolina or Delaware produce a higher
success rate for this household") from Monte Carlo sampling noise that
would otherwise dominate a smaller effect size if each candidate drew its
own independent random paths.

### 6.8 Monte Carlo simulation

- **Parametric mode**: correlated-normal draws for an equity/bond blend,
  consuming one `random.Random(seed)` instance in a fixed, deterministic
  order (path 0's years, then path 1's, ...) — same seed always produces
  the same paths.
- **Historical-bootstrap mode**: moving-block resampling from an annual
  real-return series, instead of only parametric normal draws, to capture
  fat tails and genuine historical sequencing. Not yet exposed through the
  BFF or Streamlit UI (rp-xxp) — every BFF-triggered run uses parametric
  mode only; usable today only by a caller reaching
  `retirement_planner.simulation.generate_historical_bootstrap_paths()`
  directly.
- **Sequence-of-returns stress overlay**: a configurable shock (magnitude,
  duration, and starting point within the plan) layered onto either
  return-generation mode, since a bad early sequence of returns is a
  materially different risk than the same average return spread evenly.
  Not yet exposed through the BFF or Streamlit UI (rp-xxp) — usable today
  only by a caller reaching
  `retirement_planner.simulation.apply_stress_scenario()` directly.
- **Survival-adjusted scoring** (optional, rp-9vl): success rate can be
  expressed as "probability of not running out of money while at least
  one spouse is alive," using per-member actuarial survival curves,
  instead of a single fixed planning horizon for every path. This is a
  *post-hoc* metric — it never changes what a path actually funds, only
  whether a shortfall on that path still counts as a failure once both
  members are presumed deceased (a fixed ≥50%-survival-probability
  threshold, checked once at that path's own shortfall year). Opt-in via
  `survival_adjusted: true` on a `/simulations` or `/comparisons/simulated`
  request, or the "Score success using survival-adjusted probability"
  checkbox on the Run Simulation/Compare pages — every household member is
  scored against `simulation.SURVIVAL_TABLE`'s illustrative curves (§6.9;
  there is no per-scenario user-entered survival-curve data yet). A member
  whose age falls outside that table's documented 50-110 coverage at any
  point in the run's horizon is rejected with a clear error rather than a
  bare crash.
- **Per-path probabilistic death draws** (optional, core-library-only —
  rp-vgv): unlike survival-adjusted scoring above, this capability
  changes what each path actually funds. Given the same per-member
  actuarial survival curves, each path draws its own death age per
  covered member — conditioned on that member's current age, so the
  drawn age is always plausible (never earlier than today) — and is
  funded and scored as if that death actually happened on schedule,
  reusing §6.2c's filing-status/Social-Security/spending-reduction switch
  unchanged. A path's own `success_rate` and ending-balance percentile
  bands therefore already reflect survivor-scenario risk, rather than
  requiring the separate metric above. Off by default; a caller opts in
  by pre-generating one draw set (`generate_death_age_draws()`, its own
  independent random seed, decoupled from the return-path draws) and
  reusing it, path-for-path, across every candidate in a comparison —
  identical to how return paths are already shared across candidates.
  Not yet exposed through the BFF or Streamlit UI — usable only by a
  caller reaching the core `retirement_planner.simulation` package
  directly, the same current limitation as historical-bootstrap return
  generation and the sequence-of-returns stress overlay above.

### 6.9 What's synthetic, not real, in the simulation engine

`simulation/historical_data.py`'s return series and
`simulation/survival_data.py`'s mortality table are both explicitly
**synthetic placeholder data**, generated deterministically for
structural completeness (constitution Principle V — this project has no
runtime network access to fetch a real series, and none was fetched at
authoring time either). Both ship `verified=False` and must not be
presented as real historical returns or real actuarial mortality data
until replaced with an actual, cited source. Per-path probabilistic death
draws (§6.8) sample directly from this same synthetic mortality table —
every drawn death year this capability produces is therefore no more
reliable than the illustrative curve it came from, exactly like
survival-adjusted scoring already was.

## 7. Known Limitations & Open Items

- Only 4 of the 9 states the reference use case names (§2.3) have real
  tax modules; the rest are follow-on work against the existing
  `compute_state_tax()` interface.
- South Carolina's and Delaware's bracket/exclusion figures remain
  unverified placeholders (§5.4).
- North Carolina's module does not model the Bailey settlement
  (§5.4) — a household whose income includes a pre-8/12/1989-vested
  government/military pension will see it taxed as ordinary income,
  overstating their true NC tax liability.
- The historical return series and survival/mortality curves used by the
  simulation engine are synthetic, not real published data (§6.9).
- The Joint Life and Last Survivor RMD table covers only a handful of age
  pairs and is unverified (§5.3).
- RMD start age is modeled as a tax-year step, not the statute's true
  birth-year cohort rule (§5.1).
- No CLI or notebook entry point exists yet — the tool is used via the
  Streamlit UI, the BFF's HTTP API directly, or as an importable library
  (`docs/remaining_scope.md` §2).
- Federal tax assumes every household takes the standard deduction (§5.1);
  itemizing and the temporary OBBBA senior bonus deduction are not modeled
  (§5.3).
- A configured spouse's death changes a deterministic or
  strategy-comparison projection's filing status, Social Security income,
  and spending need mid-horizon (§6.2c). By default, Monte Carlo
  simulation still applies that same switch identically to every path
  (the household's static configured death year, if any); an opt-in,
  core-library-only capability (§6.8) instead lets each path draw its own
  probabilistic death year — not yet exposed through the BFF or Streamlit
  UI, so a user of the app itself cannot turn it on. Also not modeled,
  under either behavior: Qualifying Surviving Spouse status / a joint
  return specifically for the year of death, remarriage, a detailed
  post-death budget re-plan beyond the single configured spending
  percentage, correlation between a path's own market returns and its
  drawn death year (or between the two members' own drawn death years),
  and a second (the survivor's own, later) configured or drawn death
  ending the projection (§6.2c, §6.8).
- Roth conversion five-year seasoning tracking (§6.6) now feeds a real
  10% early-withdrawal penalty (§6.6a). Still not modeled: per-member
  Roth ownership attribution (a conservative household-level age check is
  used instead — §6.6); a per-path probabilistic seasoning outcome in
  Monte Carlo simulation (every path uses the same deterministic
  conversion history a plain projection would); and the separate
  account-level rule governing whether Roth *earnings* (growth, as
  distinct from converted principal) are a "qualified distribution."
- The 10% early-withdrawal penalty (§6.6a) does not model a 72(t)/SEPP
  substantially-equal-periodic-payment alternative, nor any real IRC
  §72(t)(2) exception beyond age 59½ (disability, medical expenses,
  higher education, a first-time homebuyer's up to $10,000, health
  insurance premiums while unemployed, an IRS levy, qualified reservist
  distributions, birth/adoption up to $5,000, terminal illness, disaster
  relief, and others) — a household actually covered by one of these in
  reality will see this tool report a penalty it cannot yet suppress.
- Baseline Medicare Part B/D premiums and pre-Medicare ACA marketplace
  premiums/subsidies are not modeled (§2.2, §6.4) — only the IRMAA
  surcharge above the standard Medicare premium is. A household must
  estimate and fold both into `annual_need_real` itself; a follow-up
  feature may model either directly in the future (rp-1pp).
- **Two Monte Carlo capabilities are engine-complete but not yet reachable
  through the app itself** (rp-xxp full-surface audit; a third,
  survival-adjusted success scoring, was closed by rp-9vl — see §6.8):
  historical-bootstrap return generation and the sequence-of-returns
  stress overlay both exist in `retirement_planner.simulation` and are
  exercised by that package's own tests, but `services/bff`'s request
  schemas never accept a `generation_mode` or a stress-scenario
  configuration, and no Streamlit page offers a control for either — a
  user of the deployed app can only ever run parametric, unstressed
  simulations today. Follow-on work (rp-741, rp-2bn) is scheduled to
  expose both behind an "Advanced" section, a shock/return-model choice
  most single households won't need on a first run.

## 8. Non-Functional Requirements

From `.specify/memory/constitution.md`, evaluated for every feature
before it's considered complete:

| Principle | Requirement |
|---|---|
| Accuracy over cleverness | Every simplification (a blended rate, a flat real-dollar bracket, an unverified figure) is documented in code and surfaced in output — never presented as settled when it isn't. |
| Reproducibility | Same scenario + same random seed → identical results, every time, on every run. |
| Auditability | Every externally-sourced figure carries a citation, a last-verified date, and a visible verified/unverified flag that propagates all the way into report and chart output. |
| Extensibility | Adding a state, a withdrawal strategy, or a conversion strategy is additive against a documented interface — it never requires touching the simulation core. |
| Offline-first | The engine runs entirely offline once a scenario is configured; any rate lookup or verification pass is a separate, explicit, human-invoked action, never a runtime dependency. |
| Performance budget | The reference-scale simulation (3,000–5,000 Monte Carlo paths × every candidate state) completes in well under a minute on a standard laptop. |

## 9. Success Criteria

- A household can answer all three questions in §1 for its own scenario
  without editing engine code — only YAML configuration.
- Every number in a report is either cited and verified, or visibly
  flagged as not yet verified — never ambiguous between the two.
- Adding IRS's next annual bracket/limit update, or a new candidate
  state, is a data change plus a citation, not a redesign.
- A comparison across states, strategies, or claiming ages isolates the
  dimension being compared from simulation noise (§6.7), so a reported
  difference is attributable to the actual input change.

## 10. Source Documents & Traceability

- `docs/initial_requirement.md` — the original business ask this BRD
  formalizes and updates against delivered scope.
- `docs/remaining_scope.md` — a section-by-section reconciliation of that
  original ask against what had shipped as of `specs/001`–`005` (now
  partially superseded by `006`–`014`; kept for historical traceability).
- `specs/001`–`023` — the full spec → plan → tasks → implementation
  record for every feature; each spec's own Functional Requirements are
  the authoritative, testable statement of what that feature does.
- `.specify/memory/constitution.md` — the non-functional principles every
  plan is checked against (§8 above).
- `docs/SOLUTION_ARCHITECTURE.md` — how the system delivering all of the
  above is actually put together.
- `docs/RUNBOOK.md` — how to actually run and operate that system day to
  day.
