# Business Requirements Document: Retirement Planner

**Status**: Living document — reflects the codebase as of `specs/001`–`014`
**Last reviewed against**: `014-figure-verification` (rp-9wi)

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

### 2.3 Reference use case

The tool's acceptance baseline (`docs/initial_requirement.md` §2): a
married-filing-jointly household with Traditional IRA, Roth IRA, and
Social Security income (two independent claiming ages), a defined Roth
conversion bridge window, evaluated across a candidate set of states with
materially different tax mechanics (zero-income-tax, exclusion-based,
graduated-bracket). Only 3 of that original 9-state candidate set (South
Carolina, Delaware, Florida) have real tax modules today — the rest
(Georgia, North Carolina, Tennessee, Mississippi, Pennsylvania, New
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
| Social Security taxability thresholds | 26 U.S.C. §86(c)(1)-(2) (fixed since 1983, not inflation-indexed) | `tax/social_security.py` |
| Net Investment Income Tax (NIIT) rate & thresholds | 26 U.S.C. §1411(a)(1), (b)(1)/(3) (fixed by statute) | `tax/niit.py` |
| Medicare IRMAA surcharge tiers (Parts B & D, combined) | CMS.gov, 2026 IRMAA tables (CMS-8089-N/8090-N/8091-N) | `tax/irmaa.py` |
| HSA contribution limits (self-only, family, 55+ catch-up) | IRS Rev. Proc. 2025-19, tax year 2026 (catch-up fixed by IRC §223(b)(3)) | `mechanics/hsa.py` |
| RMD start age, including the scheduled 2033 73→75 step | 26 U.S.C. §401(a)(9)(C)(v), as amended by SECURE 2.0 Act (Pub. L. 117-328) §107 | `mechanics/rmd.py` |
| Uniform Lifetime Table (RMD divisors, ages 72–120+) | IRS Pub. 590-B (2025), Appendix B, Table III | `mechanics/rmd.py` |
| Single Life Expectancy Table (inherited-account divisors, ages 0–120+) | IRS Pub. 590-B (2025), Appendix B, Table I | `mechanics/inherited_rmd.py` |
| Social Security claiming-age early-reduction/delayed-credit rates | 42 U.S.C. §402(q)/(w); 20 C.F.R. §404.410/§404.313 (fixed by regulation, not annually revised) | `mechanics/social_security_benefit.py` |

**Simplification, documented not hidden**: the RMD start-age step above is
modeled as a tax-year cutoff (73 before 2033, 75 from 2033 on), not the
statute's actual birth-year cohort rule (age 73 for those born 1951–1959,
age 75 for 1960+). Full cohort modeling would require threading the
account owner's birth year through `compute_rmd()`'s locked signature — a
larger, separately-scoped change (`014-figure-verification`, research.md
§3).

### 5.2 Federal — real math, "real-dollar" bracket/tier convention

Federal brackets and IRMAA tiers are pinned to one specific, cited tax
year (2026) and held flat across every documented year rather than
re-indexed annually — the same "real (inflation-adjusted) dollars, no
further indexing engine" convention `tax/federal.py`'s own docstring
establishes and `tax/irmaa.py` explicitly reuses. This is an explicit,
documented assumption (constitution Principle I), not silently absorbed
imprecision: a multi-decade projection uses today's real-dollar bracket
edges throughout, rather than projecting a nominal-dollar inflation
schedule this tool has no separate model for.

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
- **Social Security spousal and survivor benefits** — each member's
  claiming-age-adjusted benefit (§6.2a) is computed entirely
  independently; a lower-earning spouse's benefit floor derived from the
  higher earner's PIA, and the higher-of-two-continues/lower-stops
  survivor rule after one spouse's death, are not modeled (tracked
  separately: rp-52n, rp-g8y).
- **Social Security earnings test** — a member who claims while still
  working before FRA is not subject to the benefit withholding the
  earnings test would impose; the tool assumes full, unwithheld payment
  from the configured claiming age on.

### 5.4 State — South Carolina, Delaware, Florida

| State | Structure | Verification status |
|---|---|---|
| Florida (FL) | No state income tax — always returns $0, consults no figures | Trivially exact by definition; no citation needed (`tax/state/fl.py`) |
| South Carolina (SC) | Graduated brackets + age-65 retirement-income exclusion | **Unverified placeholder** — round numbers in the right order of magnitude, not the real SC Code figures (`tax/state/sc.py`) |
| Delaware (DE) | Graduated brackets + age-60 retirement-income exclusion | **Unverified placeholder** — same status as SC (`tax/state/de.py`) |

South Carolina and Delaware were **not** in scope for `014-figure-verification` — that effort covered only the 8 federal figures a specific run flagged. Verifying SC/DE against South Carolina and Delaware statutory text is tracked as separate, not-yet-scheduled follow-on work.

### 5.5 Inherited retirement accounts (SECURE Act / SECURE 2.0)

Covers the 10-year rule and its exceptions, per `mechanics/inherited_rmd.py`
(`012-inherited-ira-rmd`, extended by `013-inherited-ira-edge-cases`):

- **Non-eligible designated beneficiary** (the common case since the
  original SECURE Act): full account depletion by the 10th calendar year
  after the owner's death; an annual RMD is additionally required for
  years 1–9 if the original owner had already reached their own Required
  Beginning Date (RBD) before death.
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

Explicitly not modeled: spousal benefits (a lower-earning spouse's
benefit derived from the higher earner's PIA), survivor benefits (the
higher of two benefits continuing after one spouse's death, while the
lower one stops), and the Social Security earnings test for a member who
claims while still working before FRA — tracked as known gaps, not
silently assumed away.

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
  fat tails and genuine historical sequencing.
- **Sequence-of-returns stress overlay**: a configurable shock (magnitude,
  duration, and starting point within the plan) layered onto either
  return-generation mode, since a bad early sequence of returns is a
  materially different risk than the same average return spread evenly.
- **Survival-adjusted scoring** (optional): success rate can be expressed
  as "probability of not running out of money while at least one spouse
  is alive," using per-member actuarial survival curves, instead of a
  single fixed planning horizon for every path.

### 6.9 What's synthetic, not real, in the simulation engine

`simulation/historical_data.py`'s return series and
`simulation/survival_data.py`'s mortality table are both explicitly
**synthetic placeholder data**, generated deterministically for
structural completeness (constitution Principle V — this project has no
runtime network access to fetch a real series, and none was fetched at
authoring time either). Both ship `verified=False` and must not be
presented as real historical returns or real actuarial mortality data
until replaced with an actual, cited source.

## 7. Known Limitations & Open Items

- Only 3 of the 9 states the reference use case names (§2.3) have real
  tax modules; the rest are follow-on work against the existing
  `compute_state_tax()` interface.
- South Carolina's and Delaware's bracket/exclusion figures remain
  unverified placeholders (§5.4).
- The historical return series and survival/mortality curves used by the
  simulation engine are synthetic, not real published data (§6.9).
- The Joint Life and Last Survivor RMD table covers only a handful of age
  pairs and is unverified (§5.3).
- RMD start age is modeled as a tax-year step, not the statute's true
  birth-year cohort rule (§5.1).
- No CLI or notebook entry point exists yet — the tool is used via the
  Streamlit UI, the BFF's HTTP API directly, or as an importable library
  (`docs/remaining_scope.md` §2).

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
- `specs/001`–`014` — the full spec → plan → tasks → implementation
  record for every feature; each spec's own Functional Requirements are
  the authoritative, testable statement of what that feature does.
- `.specify/memory/constitution.md` — the non-functional principles every
  plan is checked against (§8 above).
- `docs/SOLUTION_ARCHITECTURE.md` — how the system delivering all of the
  above is actually put together.
