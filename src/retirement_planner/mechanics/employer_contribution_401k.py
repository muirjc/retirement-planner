"""Employer 401(k) contribution -- match and discretionary lump sum
(rp-04u).

compute_employer_contribution() computes each household member's own
employer-funded 401(k) money for one plan year, building on rp-wei.1's own
compute_401k_contribution() output (the employee's already-§402(g)-capped
pretax+Roth contribution) rather than re-deriving eligibility or limits
independently:

- **Match**: matched_contribution = min(that member's own employee
  contribution total, match_cap_pct_of_pay * earned_income_this_year);
  match_amount = match_rate * matched_contribution.
- **Lump sum**: the configured lump_sum_annual_amount as-is, a flat
  employer contribution with no link to the employee's own deferral at
  all (e.g. a discretionary end-of-year profit-sharing deposit).

Both pieces are gated on the same member-eligibility rp-wei.1 already
established (earned_income_this_year > 0 -- an employer contributes to an
active, earning employee's account). Neither piece is excluded from the
§402(g) elective-deferral limit (that limit applies only to the employee's
own deferral, already enforced in compute_401k_contribution()) -- instead,
the IRS §415(c) "annual additions" limit caps the COMBINED total (employee
contribution + match + lump sum) per member. When the combined total would
exceed that limit, lump sum is trimmed first, then match -- the employee's
own already-§402(g)-capped contribution is never re-opened or reduced
here. Never raises for "no employer contribution configured",
"ineligible", or "over the §415(c) limit" -- caps and sets
rejected_reason, the same never-raise discipline compute_401k_contribution()
already established.

The dollar limit below is a PLACEHOLDER, not yet cross-checked against a
real IRS Revenue Procedure for tax year 2026 (same unverified status as
contribution_401k.py's own §402(g) figure) -- shipped verified=False
pending a 014-figure-verification-style follow-on pass. Mirrors that
module's own "only consult the limit when actually relevant" discipline:
the §415(c) figure is only looked up (and only reported in figures_used)
when at least one member has a nonzero raw match or lump sum amount --
a household using neither piece never surfaces this second placeholder
figure, preserving its exact prior reporting output.

Not modeled (documented simplification, docs/BRD.md §6.2f/§7): real IRC
§415(c) law excludes age-50+ catch-up dollars from the counted total
(IRC §414(v)(3)) -- this module checks the employee's FULL contribution
(base + catch-up) + match + lump sum against the placeholder limit,
without separating out the catch-up portion.

See /home/jmuir/.claude/plans/rustling-chasing-cat.md for the full rp-04u
design (this module implements that plan's Phase 1, rp-04u.1).
"""

from __future__ import annotations

from datetime import date

from retirement_planner.tax import FigureUsage, SourcedFigure

from .models import Contribution401kMemberResult, EmployerContributionMemberResult, EmployerContributionResult

_DOCUMENTED_YEARS = range(2020, 2075)

_415C_LIMITS: SourcedFigure[float] = SourcedFigure(
    name="415c_total_additions_limit",
    schedule={year: 72_000.0 for year in _DOCUMENTED_YEARS},
    citation=(
        "IRS §415(c) annual additions limit (combined employee + employer "
        "contributions) under IRC §415(c)(1)(A), tax year 2026 "
        "(PLACEHOLDER -- pending Rev. Proc. confirmation; a "
        "014-figure-verification-style follow-on is required before this "
        "figure ships verified=True). Does not separately exclude age-50+ "
        "catch-up dollars from the counted total, unlike the real statute "
        "(IRC §414(v)(3)) -- a documented v1 simplification."
    ),
    last_verified=date(2026, 9, 17),
    verified=False,
)


def compute_employer_contribution(
    contribution_results: list[Contribution401kMemberResult],
    employer_plans: dict[str, tuple[float, float, float] | None],
    member_earned_income: dict[str, float],
    tax_year: int,
) -> EmployerContributionResult:
    """contribution_results is rp-wei.1's own compute_401k_contribution()
    output (one Contribution401kMemberResult per household member).
    employer_plans maps person_name -> that member's own configured
    (match_rate, match_cap_pct_of_pay, lump_sum_annual_amount) -- or None
    if that member has no employer_contribution configured at all. Mirrors
    compute_401k_contribution()'s own configured_amounts convention
    (plain tuples, never a scenario-layer dataclass, to keep mechanics/
    independent of scenario/). member_earned_income maps person_name ->
    that member's own earned_income_this_year (the same dict projection.py
    already threads through compute_401k_eligibility()).

    Eligible iff earned_income_this_year > 0 (same gate rp-wei.1 already
    established) -- an ineligible or unconfigured (plan is None) member
    always gets 0.0 for both match_amount and lump_sum_amount.
    """
    raw: list[tuple[Contribution401kMemberResult, float, float, bool]] = []
    for c in contribution_results:
        plan = employer_plans.get(c.person_name)
        earned_income_this_year = member_earned_income.get(c.person_name, 0.0)
        eligible = earned_income_this_year > 0

        if plan is None or not eligible:
            raw.append((c, 0.0, 0.0, eligible))
            continue

        match_rate, match_cap_pct_of_pay, lump_sum_annual_amount = plan
        employee_contribution = c.pretax_contributed + c.roth_contributed
        matched_contribution = min(employee_contribution, match_cap_pct_of_pay * earned_income_this_year)
        raw_match = match_rate * matched_contribution
        raw.append((c, raw_match, lump_sum_annual_amount, eligible))

    any_relevant = any(match > 0.0 or lump_sum > 0.0 for _, match, lump_sum, _ in raw)

    if not any_relevant:
        member_results = [
            EmployerContributionMemberResult(
                person_name=c.person_name,
                eligible=eligible,
                matched_contribution=0.0,
                match_amount=0.0,
                lump_sum_amount=0.0,
                rejected_reason=(None if eligible else "no earned_income this plan year"),
            )
            for c, _, _, eligible in raw
        ]
        return EmployerContributionResult(
            member_results=member_results,
            total_match=0.0,
            total_lump_sum=0.0,
            figures_used=[],
        )

    limits_figure = _415C_LIMITS
    limit = limits_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used: list[FigureUsage] = [limits_figure.usage_for_year(tax_year)]

    member_results = []
    for c, raw_match, raw_lump_sum, eligible in raw:
        plan = employer_plans.get(c.person_name)

        if plan is None or not eligible:
            member_results.append(
                EmployerContributionMemberResult(
                    person_name=c.person_name,
                    eligible=eligible,
                    matched_contribution=0.0,
                    match_amount=0.0,
                    lump_sum_amount=0.0,
                    rejected_reason=(None if eligible else "no earned_income this plan year"),
                )
            )
            continue

        _, match_cap_pct_of_pay, _ = plan
        earned_income_this_year = member_earned_income.get(c.person_name, 0.0)
        employee_contribution = c.pretax_contributed + c.roth_contributed
        matched_contribution = min(employee_contribution, match_cap_pct_of_pay * earned_income_this_year)
        combined = employee_contribution + raw_match + raw_lump_sum

        if combined <= limit:
            member_results.append(
                EmployerContributionMemberResult(
                    person_name=c.person_name,
                    eligible=True,
                    matched_contribution=matched_contribution,
                    match_amount=raw_match,
                    lump_sum_amount=raw_lump_sum,
                    rejected_reason=None,
                )
            )
            continue

        excess = combined - limit
        lump_sum_amount = max(0.0, raw_lump_sum - excess)
        remaining_excess = max(0.0, excess - raw_lump_sum)
        match_amount = max(0.0, raw_match - remaining_excess)
        member_results.append(
            EmployerContributionMemberResult(
                person_name=c.person_name,
                eligible=True,
                matched_contribution=matched_contribution,
                match_amount=match_amount,
                lump_sum_amount=lump_sum_amount,
                rejected_reason=(
                    f"combined employee + employer total {combined:.2f} exceeds the §415(c) "
                    f"limit {limit:.2f} for {tax_year} -- capped (lump sum trimmed first, then "
                    f"match; the employee's own contribution is never reduced here)"
                ),
            )
        )

    return EmployerContributionResult(
        member_results=member_results,
        total_match=sum(r.match_amount for r in member_results),
        total_lump_sum=sum(r.lump_sum_amount for r in member_results),
        figures_used=figures_used,
    )
