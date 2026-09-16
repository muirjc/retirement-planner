"""401(k)/Roth 401(k) elective-deferral contribution eligibility and limit
calculation (rp-wei).

compute_401k_eligibility() determines each household member's eligibility
independently: eligible iff that member has earned_income this plan year
(IRC §402(g) -- an elective deferral is withheld from wages, so a member
with no wages this year has nothing to defer). compute_401k_contribution()
then looks up the applicable IRS elective-deferral limit -- unlike HSA's
household-pooled self-only/family tiers, this limit applies per person
(IRC §402(g) is an individual limit), plus a per-eligible-member 50+
catch-up -- and caps that member's configured pretax+Roth intent at
min(applicable_limit, that member's own earned_income_this_year) (a
member can't defer more than they earned this year, the same "can't
exceed my own wages" ceiling real payroll withholding enforces). Never
raises for the ordinary "not eligible this year" or "configured above the
limit" cases -- only for an undocumented tax_year's limit figure. When a
member's combined pretax+Roth intent exceeds their own ceiling, pretax is
capped first and Roth fills whatever headroom remains -- an arbitrary but
fixed tiebreak (no real IRS ordering rule governs this split; a real plan
election simply can't exceed the limit to begin with).

The dollar limits below are a PLACEHOLDER, not yet cross-checked against a
real IRS Revenue Procedure for tax year 2026 (contrast hsa.py's own
verified=True HSA limits) -- shipped verified=False pending a
014-figure-verification-style follow-on pass, mirroring how this
project's SC/DE tax modules originally shipped before their own
verification passes. Do not treat these figures as authoritative.

Because that limit figure is unverified, compute_401k_contribution() only
consults it (and only reports it in figures_used) when at least one
household member actually has a nonzero configured pretax or Roth
amount -- unlike hsa.py's own unconditional lookup (safe there only
because HSA's limit ships verified=True). A scenario with no 401(k)
contribution configured anywhere therefore never surfaces this
placeholder figure at all, preserving every such scenario's exact prior
reporting output.

See /home/jmuir/.claude/plans/rustling-chasing-cat.md for the full rp-wei
design (this module implements that plan's Phase 1, rp-wei.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retirement_planner.tax import FigureUsage, SourcedFigure

from .models import Contribution401kEligibility, Contribution401kMemberResult, Contribution401kResult

_DOCUMENTED_YEARS = range(2020, 2075)

_CATCH_UP_ELIGIBLE_AGE = 50


@dataclass
class _Contribution401kLimits:
    elective_deferral_limit: float
    catch_up: float


_401K_LIMITS: SourcedFigure[_Contribution401kLimits] = SourcedFigure(
    name="401k_elective_deferral_limits",
    schedule={
        year: _Contribution401kLimits(elective_deferral_limit=24_500.0, catch_up=8_000.0) for year in _DOCUMENTED_YEARS
    },
    citation=(
        "IRS elective deferral limit under IRC §402(g)(1)(B), tax year 2026 "
        "(PLACEHOLDER -- pending Rev. Proc. confirmation; a "
        "014-figure-verification-style follow-on is required before this "
        "figure ships verified=True)"
    ),
    last_verified=date(2026, 9, 16),
    verified=False,
)


def compute_401k_eligibility(
    members: list[tuple[str, int, float]],
) -> list[Contribution401kEligibility]:
    """members is a list of (person_name, age_this_year,
    earned_income_this_year). A member is eligible iff
    earned_income_this_year > 0 -- computed per member, independent of
    every other member's own value. earned_income_this_year is carried
    on the result so compute_401k_contribution() can use it as that
    member's own contribution ceiling without a second parameter
    threading it separately."""
    results = []
    for person_name, age, earned_income_this_year in members:
        if earned_income_this_year <= 0:
            results.append(
                Contribution401kEligibility(
                    person_name=person_name,
                    age=age,
                    earned_income_this_year=earned_income_this_year,
                    eligible=False,
                    reason="no earned_income this plan year",
                )
            )
        else:
            results.append(
                Contribution401kEligibility(
                    person_name=person_name,
                    age=age,
                    earned_income_this_year=earned_income_this_year,
                    eligible=True,
                    reason=None,
                )
            )
    return results


def compute_401k_contribution(
    eligibility: list[Contribution401kEligibility],
    configured_amounts: dict[str, tuple[float, float]],
    tax_year: int,
) -> Contribution401kResult:
    """configured_amounts maps person_name -> (configured
    pretax_annual_amount, configured roth_annual_amount) as the household
    intends, regardless of eligibility (an ineligible or unconfigured
    member simply contributes 0.0 either way).

    Looks up tax_year's elective-deferral limit -- but ONLY when at least
    one member has a nonzero configured pretax or Roth amount anywhere in
    configured_amounts; when nothing is configured household-wide, the
    limit is never consulted at all (figures_used stays [], and
    UnsupportedTaxYearError is never raised) -- the limit figure genuinely
    didn't matter to this year's output, so it isn't reported as having
    been used. This matters concretely because the limit figure ships
    verified=False (a placeholder): unconditionally reporting it every
    plan year regardless of configuration, the way hsa.py's own verified
    limit safely does, would make every scenario -- including every one
    that never configures a 401(k) contribution at all -- show an
    "unverified figure" in reporting, breaking this feature's own
    default-preserving requirement.

    When something IS configured: for each eligible member,
    applicable_limit = elective_deferral_limit + (catch_up if age >= 50
    else 0.0); that member's own effective ceiling is further capped at
    their own earned_income_this_year (can't defer more than you earned).
    If the member's configured pretax+Roth total fits under that
    ceiling, both amounts are contributed as configured. Otherwise
    pretax is capped first (up to the ceiling), and Roth fills whatever
    headroom remains -- never raises, sets rejected_reason instead. An
    ineligible member always gets pretax_contributed=roth_contributed=0.0
    with that member's own eligibility reason.
    """
    any_configured = any(pretax != 0.0 or roth != 0.0 for pretax, roth in configured_amounts.values())

    if not any_configured:
        member_results = [
            Contribution401kMemberResult(
                person_name=e.person_name,
                age=e.age,
                eligible=e.eligible,
                applicable_limit=0.0,
                pretax_contributed=0.0,
                roth_contributed=0.0,
                rejected_reason=e.reason if not e.eligible else None,
            )
            for e in eligibility
        ]
        return Contribution401kResult(
            member_results=member_results,
            total_pretax_contributed=0.0,
            total_roth_contributed=0.0,
            figures_used=[],
        )

    limits_figure = _401K_LIMITS
    limits = limits_figure.value_for_year(tax_year)  # raises UnsupportedTaxYearError
    figures_used: list[FigureUsage] = [limits_figure.usage_for_year(tax_year)]

    member_results = []

    for e in eligibility:
        configured_pretax, configured_roth = configured_amounts.get(e.person_name, (0.0, 0.0))

        if not e.eligible:
            member_results.append(
                Contribution401kMemberResult(
                    person_name=e.person_name,
                    age=e.age,
                    eligible=False,
                    applicable_limit=0.0,
                    pretax_contributed=0.0,
                    roth_contributed=0.0,
                    rejected_reason=e.reason,
                )
            )
            continue

        applicable_limit = limits.elective_deferral_limit + (limits.catch_up if e.age >= _CATCH_UP_ELIGIBLE_AGE else 0.0)
        effective_ceiling = min(applicable_limit, e.earned_income_this_year)
        configured_total = configured_pretax + configured_roth

        if configured_total <= effective_ceiling:
            member_results.append(
                Contribution401kMemberResult(
                    person_name=e.person_name,
                    age=e.age,
                    eligible=True,
                    applicable_limit=applicable_limit,
                    pretax_contributed=configured_pretax,
                    roth_contributed=configured_roth,
                    rejected_reason=None,
                )
            )
            continue

        pretax_contributed = min(configured_pretax, effective_ceiling)
        roth_contributed = min(configured_roth, effective_ceiling - pretax_contributed)
        member_results.append(
            Contribution401kMemberResult(
                person_name=e.person_name,
                age=e.age,
                eligible=True,
                applicable_limit=applicable_limit,
                pretax_contributed=pretax_contributed,
                roth_contributed=roth_contributed,
                rejected_reason=(
                    f"configured total {configured_total:.2f} exceeds the applicable "
                    f"limit {effective_ceiling:.2f} for {tax_year} -- capped (pretax first, "
                    f"Roth filling remaining headroom)"
                ),
            )
        )

    return Contribution401kResult(
        member_results=member_results,
        total_pretax_contributed=sum(r.pretax_contributed for r in member_results),
        total_roth_contributed=sum(r.roth_contributed for r in member_results),
        figures_used=figures_used,
    )
