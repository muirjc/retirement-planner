# Research: Inherited-IRA edge cases (rp-c8b, rp-iju, rp-l4d)

012-inherited-ira-rmd's own research.md §9 named three follow-on cases,
each requiring "its own research pass": Roth inherited IRAs (rp-c8b),
eligible-designated-beneficiary (EDB) computation (rp-iju), and pre-RBD
inherited traditional IRAs (rp-l4d). All three modify the same function
(`compute_inherited_rmd()`) and the same validation flags, so — following
`010-advanced-tax-benefits`'s own precedent of bundling several related
sub-features sharing one implementation surface under one spec number —
they are researched and delivered together here, while remaining three
separate `bd` issues (each closed with its own summary).

Primary source for every rule below: **IRS Publication 590-B (2025),
Chapter 1** (https://www.irs.gov/pub/irs-pdf/p590b.pdf), pp. 8–11
("IRA Beneficiaries" / "Owner Died on or After Required Beginning Date" /
"Owner Died Before Required Beginning Date" / "10-year rule" /
"Figuring the Beneficiary's RMD") — the same PDF already fetched and
verified against for rp-6c5's Table I fix.

## 1. Pre-RBD, non-EDB (rp-l4d): no annual RMD, full depletion at year 10

**Decision**: When the beneficiary is *not* an eligible designated
beneficiary and the original owner died before their RBD,
`compute_inherited_rmd()` returns `required_amount=0.0`,
`table_used=None`, `divisor=None` for every year before the 10-year
deadline — the deadline itself (`death_year + 10`, unchanged from
012) is still enforced entirely by the caller's existing pre-check
(`comparison/projection.py`'s `tax_year >= inherited_account.depletion_deadline_year`
branch), never inside this function.

**Rationale**: Pub. 590-B, p. 10: *"Payment under the 10-year rule. If
the IRA owner dies before the required beginning date and the 10-year
rule applies, no distribution is required for any year before the 10th
year."* This is the exact case `rp-l4d`'s own description names.

## 2. Roth inherited IRAs (rp-c8b): identical computation to §1

**Decision**: A Roth account (`account_type == "roth"`) is always treated
as pre-RBD for this computation, **regardless of** whatever
`InheritedIraDetails.decedent_was_taking_rmds` a scenario author entered
for it — the field describes a fact about the *decedent*'s RMD history,
and a Roth owner's RMD history during their own lifetime is never
"started" under IRS rules, so the field cannot honestly be `True` for a
Roth account. `compute_inherited_rmd()` derives one internal boolean,
`owner_died_before_rbd = (account_type == "roth") or (not decedent_was_taking_rmds)`,
and every branch below keys off that boolean, not `decedent_was_taking_rmds`
directly — so §1's "no annual RMD, full depletion at year 10" behavior
applies to a non-EDB Roth beneficiary exactly as it does to a pre-RBD
traditional one.

**Rationale**: *"A Roth IRA is treated the same [for distribution rules]
whether the owner had reached the required beginning date or not — Roth
IRA owners are always treated as having died before their required
beginning date"* is the standard, uncontested reading of 26 U.S.C.
§408A(c)(5) (Roth IRAs carry no lifetime RMD for the owner) combined
with Pub. 590-B's own owner-died-before-RBD rules — 012's own §9.4
already anticipated this exact conclusion ("no annual RMDs are required
during the 10-year window at all, but full depletion by year 10 still
applies").

**Alternatives considered**: A separate, duplicated "Roth" branch
re-implementing §1's logic — rejected; deriving one shared boolean keeps
the two cases from silently drifting apart, and makes the *reason*
they're identical (both are "deemed pre-RBD") explicit in code, not just
coincidental.

## 3. EDB annual "stretch" RMD (rp-iju), post-RBD: the "longer of" rule

**Decision**: For any eligible designated beneficiary (spouse or other)
when the original owner died on/after RBD, the annual required amount
uses the **longer of** (a) the beneficiary's own single life expectancy,
or (b) the owner's remaining life expectancy — i.e. `divisor =
max(divisor_beneficiary, divisor_owner)` (a larger divisor is a *longer*
life expectancy, producing a *smaller* required distribution). Both
candidate divisors use the existing "look up once, reduce by 1.0 each
subsequent year" method (never a fresh lookup) — **except** a spouse's
own-life-expectancy candidate, which is recalculated fresh every year at
the spouse's then-current age (§4). `divisor_owner` reuses 012's
existing formula unchanged (`decedent_age_at_death` at `death_year + 1`,
decremented by 1/year).

**Rationale**: Pub. 590-B, p. 9: *"If the owner died on or after their
required beginning date... and you are a designated beneficiary, base
your required minimum distributions for years after the year of the
owner's death on the longer of: Your single life expectancy...; or The
owner's life expectancy."* In the overwhelmingly common real case (an
EDB younger than the decedent — the very thing "eligible" screens for:
a spouse, a minor child, or someone not more than 10 years younger — see
Constitution note below), the beneficiary's own life expectancy is
longer, so this resolves to "use your own age's Table I divisor,"
matching well-established professional guidance; the max() only ever
selects the owner's side in the unusual case a beneficiary is *older*
than an already-RMD-taking decedent.

**A note on the already-shipped, out-of-scope non-EDB case**: this same
Pub. 590-B passage's "longer of" language is not qualified to "eligible"
designated beneficiaries only — it says "a designated beneficiary." Read
literally, the already-shipped 012 divisor logic for
`non_eligible_designated_beneficiary` + post-RBD (`inherited_rmd.py`'s
existing, unchanged code) — which uses *only* the decedent's own divisor,
never comparing it against the beneficiary's own — may be missing this
same "longer of" comparison, and in the common case (a beneficiary
younger than the already-RMD-taking decedent) would be *overstating* the
required annual distribution. This is a correctness question about
already-shipped, tested code, not part of any of `rp-c8b`/`rp-iju`/
`rp-l4d`'s own scope — filed separately as `rp-<TBD>` for a dedicated
review, rather than silently changed as a side effect of this work
(Constitution Principle I: never bundle an unrelated correctness change
into a scope-boundary fix without its own review).

## 4. EDB annual "stretch" RMD, spouse-specific rules

**Decision**: Two spouse-specific deviations from §3's general EDB
treatment:

- **Divisor**: a spouse's own-life-expectancy candidate is looked up
  *fresh* from Table I at the spouse's current age every single year
  (never decremented from an initial-year lookup) — the non-spouse EDB
  case (§3, §5) still uses the decrement-by-1 method.
- **Delayed start (pre-RBD only)**: if `owner_died_before_rbd` is true
  (§2), the spouse is not required to take any distribution until the
  year the original owner *would have* reached their own RBD —
  `decedent_rbd_year = (death_year − decedent_age_at_death) + RMD_START_AGE`
  (reusing `rmd.py`'s own existing `RMD_START_AGE` figure, looked up at
  `death_year + 1`, matching every other "year after death" anchor point
  already used elsewhere in this module). Before that year,
  `required_amount = 0.0`. From that year on, the spouse's divisor is
  looked up fresh (per above) with no comparison against the owner's
  side (there is no "owner's side" pre-RBD — see §1).

**Rationale**: Pub. 590-B, p. 9: *"Surviving spouse is sole designated
beneficiary... the applicable denominator continues to be determined
each subsequent year using Table I"* (recalculated, contrasted
explicitly against the non-spouse "reduced by one" rule two sentences
earlier). p. 10: *"the surviving spouse isn't required to begin
receiving minimum distributions until the end of the year in which the
IRA owner would have reached their required beginning date."*

**Alternatives considered**: Applying the non-spouse decrement-by-1
method to a spouse too — rejected; the primary source explicitly
distinguishes the two, and this project already has a working, tested
decrement-by-1 implementation from 012 to reuse for the non-spouse case,
so the marginal cost of also implementing the recalculating case
correctly (rather than reusing the wrong one for expedience) is small.
Reusing `rmd.py`'s `RMD_START_AGE` rather than hardcoding a spousal-delay
age — consistent with `research.md §7`'s own reasoning against
duplicating a figure this project already sources centrally, and
automatically inherits whatever `RMD_START_AGE` itself documents (73 for
every currently-documented year — the pre-existing, separately-tracked
73→75-in-2033 gap `rmd.py`'s own docstring already names, not addressed
here either).

## 5. EDB annual "stretch" RMD, non-spouse: minor child until majority

**Decision**: A minor-child EDB (`beneficiary_relationship ==
"minor_child"` and `beneficiary_classification ==
"eligible_designated_beneficiary_other"`) uses exactly §3's non-spouse
divisor formula (decrement-by-1, "longer of" if post-RBD) for every year
before they turn 21 — no special-casing needed inside
`compute_inherited_rmd()` itself for "minor" vs. any other non-spouse
EDB, since the divisor math is identical. What *does* differ is the
account's `depletion_deadline_year`: instead of the "effectively never"
sentinel a true (non-minor) EDB gets (§6), a minor child's account gets
`depletion_deadline_year = majority_year + 10`, where `majority_year` is
the tax year the beneficiary turns 21 — computed **once**, at resolution
time (`services/bff/src/rp_bff/resolution.py::_inherited_accounts()`,
the same place `death_year + 10` is already computed today), from the
beneficiary's `HouseholdMember.current_age` and the scenario's
`reference_tax_year` (`birth_year = reference_tax_year − current_age`;
`majority_year = birth_year + 21`) — the same age-anchoring arithmetic
`comparison/projection.py::member_age_in_tax_year()` already uses
elsewhere in this codebase, not a new concept.

**Rationale**: Pub. 590-B, p. 10: *"For a beneficiary receiving life
expectancy payments who is either an eligible designated beneficiary or
a minor child, the 10-year rule also applies to the remaining amounts in
the IRA upon... the child's attainment of majority. In either of those
cases, the 10-year period ends on December 31 of the year containing the
10th anniversary of... the child's attainment of majority."* Age 21 as
"majority" for this specific purpose (not a state's own age-of-majority
law) is the IRS's own final-regulation position, confirmed via a
secondary source cross-check (Fidelity/Entrust Group explainers agree,
each citing the July 2024 final regulations) since Pub. 590-B's own
prose names "attainment of majority" without repeating the number
inline. Computing `majority_year` once, at resolution time, mirrors how
`death_year + 10` is *already* a fixed, resolution-time-computed value
never re-derived per plan year (012 research.md §8's own "computed once,
held fixed for the life of the projection" pattern) — a beneficiary
turning 21 mid-projection is a fully deterministic, known-in-advance
event given their `current_age`, unlike the genuinely event-driven cases
(a household member's death) this codebase already declines to model
mid-projection (012 §1, §9.10).

**Alternatives considered**: Re-deriving `majority_year` fresh inside
`compute_inherited_rmd()` every call from `beneficiary_current_age` —
rejected; would require this pure divisor-arithmetic function to also
own deadline logic, duplicating what the resolution layer already does
for every other inherited-account deadline, and risking the two
computations drifting apart.

## 6. EDB with no minor-child transition: effectively no forced-depletion deadline

**Decision**: A spouse EDB, or a non-spouse EDB who is not a minor child,
gets `depletion_deadline_year` set to a sentinel far beyond any
realistic plan horizon (`death_year + 200`) rather than `None` —
avoiding a schema change to `InheritedAccountBalance.depletion_deadline_year`
(kept a plain `int`, not `int | None`, so every existing caller/test that
assumes a non-`None` int is untouched) while still never triggering the
"force full withdrawal" branch within any plan this project can
represent (`plan_to_age` is realistically well under 200 years past
`death_year`).

**Rationale**: True EDB stretch treatment has no 10-year deadline of its
own — Pub. 590-B's own 10-year-rule section ties the *EDB's* eventual
10-year clock to the EDB's own death ("upon the death of the eligible
designated beneficiary"), which this codebase already declines to model
mid-projection for the *original owner* (012 §1, §9.10) and, by the same
reasoning, declines to model for a *beneficiary* here too — a documented
simplification (Constitution Principle I: named explicitly, not silently
dropped), not a claim that a true EDB's inherited account can literally
never require full depletion in the real world.

**Alternatives considered**: Making `depletion_deadline_year: int | None`
and updating every consumer to handle `None` — rejected as a larger,
more invasive schema change for the same practical effect a sentinel
value achieves with zero call-site changes elsewhere.

## 7. Trust-or-entity beneficiaries: stay blocked (pre-existing gap, closed here)

**Decision**: A new fourth validation rule blocks any inherited account
whose `beneficiary_relationship == "trust_or_entity"`, regardless of
`beneficiary_classification` — closing a gap that already existed
*before* this work (012's validation only ever checked
`beneficiary_classification`, never `beneficiary_relationship`, so a
trust/entity beneficiary with `classification="non_eligible_designated_beneficiary"`
was already silently accepted and computed with ordinary-individual
10-year-rule logic). Relaxing the `beneficiary_classification` blocking
flag to allow EDB values (§3–§6 above) would, without this new rule,
newly *also* let a trust/entity beneficiary through the EDB divisor
logic — which is wrong for a trust (Pub. 590-B: *"Beneficiary not an
individual. See the 5-year rule if the owner died before the owner's
required beginning date and the beneficiary is not an individual"* — a
different rule entirely, and even for a "see-through" trust that does
qualify as EDB, whose life expectancy to use is a genuinely separate,
harder question this codebase's own taxonomy never committed to
answering, 012 research.md §3).

**Rationale**: 012 research.md §9.5 already named "multiple-beneficiary /
trust-or-entity beneficiary accounts" as explicit follow-on work, not
something this pass attempts — closing the *validation* gap (so a
trust/entity beneficiary is never silently computed as if it were an
ordinary individual) is squarely this pass's own responsibility, since
this pass is what makes the EDB pathway newly reachable at all.

## 8. Summary: revised validation rules

Of 012's four existing blocking rules (`scenario/validation.py`):

1. `decedent_was_taking_rmds is False` — **removed**; §1/§2 now compute
   this case for `non_eligible_designated_beneficiary`; still computed
   correctly for EDB per §3–§6 (the boolean only ever gated the non-EDB
   annual-RMD-vs-not question, never blocked EDB on its own).
2. `beneficiary_classification != "non_eligible_designated_beneficiary"`
   — **removed**; §3–§6 now compute both EDB classifications.
3. `account.account_type != "traditional"` — **narrowed** to `not in
   ("traditional", "roth")`; `"taxable"` inherited accounts remain
   blocked (012's own §10 addendum rationale — a taxable account has no
   IRS distribution schedule at all — is unaffected by this pass).
4. **New**: `beneficiary_relationship == "trust_or_entity"` — always
   blocking, regardless of classification (§7).

## Handoff

Implementation touches: `mechanics/models.py` (new `InheritedAccountBalance`
fields), `mechanics/inherited_rmd.py` (§1–§6's logic, new optional
parameters on `compute_inherited_rmd()`, all defaulted so the existing
non-EDB post-RBD contract and its tests are unchanged), `comparison/projection.py`
(thread the beneficiary's current age into each year's call),
`scenario/validation.py` (§8), `services/bff/src/rp_bff/resolution.py`
(§5's `majority_year` computation, §6's sentinel, `beneficiary_current_age`
threading). No change to `simulation/monte_carlo.py`/`simulation/compare.py`
beyond what `rp-mt7` already shipped — `InheritedAccountBalance`'s new
fields flow through `_fresh_inherited_accounts()`'s existing
`dataclasses.replace()` copy unchanged, since they're all flat/immutable
values, the same way its existing fields already do.
