# Phase 0 Research: Figure Verification (Placeholder Tax Figures)

## 0. Scope of this research pass

Technical Context (plan.md) left no `NEEDS CLARIFICATION` markers — this
feature makes no new technology, architecture, or dependency choice; it
corrects data inside 6 already-existing modules. What *does* need
research is domain fact-finding: for each of the 8 figures, what a
primary source actually says. That research is deliberately **not**
pre-computed and baked into this document. §1 explains why, §2 records
the per-figure research plan each implementation task (the existing
`rp-9wi.1`–`.7` beads) follows, and §3 covers the one figure
(`rmd_start_age`) with an actual design decision behind it rather than a
pure lookup.

## 1. Decision: primary-source lookups happen at implementation time, not baked into this planning artifact

**Decision**: This document does not assert specific dollar figures,
percentages, or table values as "the verified answer" for any of the 8
figures. Each implementation task performs its own live lookup against
the source named in §2 at the time that task is actually done.

**Rationale**: Three of this project's own principles converge on this:

- **Auditability (Constitution III)** requires a figure be "cross-checked
  against a primary source" before being marked verified — a number typed
  into a planning document from memory, however plausible, is exactly the
  kind of unverified figure this whole feature exists to eliminate. The
  cross-check has to happen at the point the figure is actually written
  into source and cited, so the citation and the check are inseparable.
- **Reproducibility/staleness**: a Rev. Proc. or CMS.gov table "current"
  when this plan was written may not be the most recent one available by
  the time a given `rp-9wi.N` bead is actually implemented (these publish
  on their own annual cadence, not this project's). Pinning a year now
  would risk shipping a citation that was already stale on arrival.
- **Offline-First (Constitution V)**: the lookup is explicitly a one-time,
  human/agent-invoked research step baked into source as a literal +
  citation afterward — never a runtime dependency. Doing it once, at
  implementation time, for each figure, is that same pattern; doing it
  twice (once speculatively here, once for real later) adds risk of the
  two disagreeing without adding any actual value.

**Alternatives considered**: Perform the live lookups now and record
findings directly in this research.md. Rejected for the staleness and
duplicated-effort reasons above — and because each figure already has its
own tracked bead (`rp-9wi.1`–`.7`) that is the natural place to record
"looked this up on [date], here's what the primary source said," matching
`rp-6c5`'s own close-reason precedent (which recorded its actual PDF
page cross-check in the bead's close reason, not in a spec artifact).

## 2. Per-figure research plan (Groups A/B, pure re-citation)

| Figure | File | Primary source to check | What "verified" means here |
|---|---|---|---|
| `niit_rate`, `niit_threshold_mfj`, `niit_threshold_single` | `tax/niit.py` | 26 U.S.C. §1411 (statute text — Cornell LII or govinfo.gov) | Confirm 3.8% rate and $250k/$200k thresholds are still what the statute states (fixed since enactment, not inflation-indexed) — cite the specific subsection. |
| `ss_provisional_income_thresholds_mfj`, `_single` | `tax/social_security.py` | 26 U.S.C. §86(c) (statute text) | Confirm $32k/$44k (MFJ) and $25k/$34k (single) — fixed since 1984, never indexed. Citations already name the specific subsections; only the dollar figures and `verified` flag need confirming. |
| `federal_brackets_mfj`, `_single` | `tax/federal.py` | Most recently published IRS Revenue Procedure setting the tax year's inflation-adjusted bracket thresholds | Pick one named, cited tax year; replace the round-number placeholder thresholds with that Rev. Proc.'s actual figures. Rate percentages (10/12/22/24/32/35/37%) are statutory and not expected to need correction — only the dollar edges are placeholders. |
| `irmaa_tiers_mfj`, `_single` | `tax/irmaa.py` | CMS.gov's published IRMAA premium tables for the most recent year | Same pattern as federal brackets: pick one named, cited year; replace placeholder tier thresholds/surcharges with that table's actual figures. |
| `hsa_contribution_limits` | `mechanics/hsa.py` | IRS Revenue Procedure announcing that year's HSA limits | Confirm self-only/family/catch-up figures against the actual Rev. Proc. — plan.md flags that today's placeholder values already resemble real recent figures, so this may turn out to be a pure re-citation, not a correction; confirm rather than assume. |
| `uniform_lifetime_table` | `mechanics/rmd.py` | IRS Pub. 590-B, Appendix B, Table III (Uniform Lifetime) — primary-source PDF | Cross-check every existing divisor (ages 72-100) against the published table (following `rp-6c5`'s precedent, where a sibling table's placeholder values were measurably wrong for a third of its range) and extend coverage through the table's full published age range. |

Each row's implementation task adds its finding — source document name,
specific section/page, the date checked, and (for Group B/C) which
literal values changed and by how much — to its bead's close reason,
mirroring `rp-6c5 close --reason=...`, and updates the module's citation
string and `last_verified` date to match.

## 3. `rmd_start_age`: schedule design, not just a lookup

Unlike the other 7 figures, `rmd_start_age` needs a structural decision,
already made during planning (spec.md Assumptions) rather than left to
implementation:

**Decision**: Model `RMD_START_AGE.schedule` as a two-part step keyed by
tax year — 73 for `tax_year < 2033`, 75 for `tax_year >= 2033` — rather
than by the account owner's birth year.

**Rationale**: SECURE 2.0 Act §107's real rule is birth-year-cohort-based
(the applicable start age depends on which cohort the owner's birth year
falls into, not the calendar year an RMD happens to be computed in).
Modeling that exactly would require threading the owner's birth year
through `compute_rmd()`'s call chain — a signature change to a function
`003`'s contract already locks, and a change to every caller. The
tax-year step is a smaller, contained change that still eliminates the
epic's core complaint (a scheduled future change silently modeled as a
flat value forever) using the same `SourcedFigure[int]` shape and the
same `schedule: dict[int, T]` mechanism every other figure in this
project already uses.

**Alternatives considered**:
- *Full birth-year cohort modeling* — more accurate, but a materially
  larger change (new parameter through `compute_rmd()` and its callers)
  than any other figure in this epic; explicitly deferred as its own
  follow-on bead once this lands (spec.md Assumptions, plan.md
  "Deliberately out of scope").
- *Leave it flat, just re-cite it as "73, current as of 2026"* — rejected
  outright by the epic's own acceptance criteria, which specifically
  singles out this figure as one that must not be "silently verified" as
  a single current-year value when the law itself schedules a change
  within the tool's documented year range (2020-2074).

**Primary source to confirm the exact 2033 date and 75 figure**: 26
U.S.C. §401(a)(9)(C), as amended by SECURE 2.0 Act (Pub. L. 117-328)
§107 — confirmed at implementation time per §1 above, same as every other
figure.
