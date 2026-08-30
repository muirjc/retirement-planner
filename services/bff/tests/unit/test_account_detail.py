"""Unit tests for rp_bff.account_detail: the thin BFF-layer wiring over
retirement_planner.reporting.account_attribution
(015-per-account-projection-detail, contracts/bff-api.md).
"""

import pytest

from retirement_planner.comparison import DeterministicReturnAssumption, StrategyConfiguration, run_plan_projection
from retirement_planner.mechanics import AccountBalances
from retirement_planner.reporting import compute_account_shares
from retirement_planner.scenario import Account, Household, HouseholdMember
from retirement_planner.simulation import SimulationRun

from rp_bff.account_detail import (
    PathIndexOutOfRangeError,
    build_account_detail_for_projection,
    build_account_detail_for_run,
    path_index_out_of_range_error,
)


def _household():
    return Household(
        filing_status="single",
        members=[HouseholdMember(person_name="you", current_age=75, ss_claim_age=99, ss_annual_benefit=0)],
    )


def _accounts():
    return [Account(account_type="taxable", balance=100_000, owner="you", account_id="taxable-0")]


def _projection(annual_real_return=0.0):
    return run_plan_projection(
        household=_household(),
        accounts=AccountBalances(traditional=0, roth=0, taxable=100_000),
        traditional_ownership_shares={"you": 0.0},
        annual_spending_need=10_000,
        state="FL",
        reference_tax_year=2026,
        start_plan_year=1,
        start_tax_year=2026,
        plan_to_age=76,
        strategy=StrategyConfiguration(
            label="test", withdrawal_strategy="rmd_taxable_traditional_roth", conversion_strategy=None,
            conversion_bracket_ceiling_or_amount=None, conversion_window=None, claiming_ages={"you": 99},
        ),
        return_assumption=DeterministicReturnAssumption(annual_real_return=annual_real_return),
    )


def test_build_account_detail_for_projection_matches_attribute_plan_projection_directly():
    from retirement_planner.reporting import attribute_plan_projection

    shares = compute_account_shares(_accounts())
    projection = _projection()

    via_bff = build_account_detail_for_projection(shares, projection)
    direct = attribute_plan_projection(projection, shares)

    assert via_bff == direct


def test_build_account_detail_for_run_defaults_to_path_zero():
    shares = compute_account_shares(_accounts())
    path_0 = _projection(annual_real_return=0.0)
    path_1 = _projection(annual_real_return=0.10)  # a different path -- different ending balances
    run = SimulationRun(
        candidate_label="test", strategy=path_0.strategy, state="FL", path_results=[path_0, path_1],
        success_rate=1.0, percentile_bands=[], survival_adjusted_success_rate=None, figures_used=[],
    )

    detail_default = build_account_detail_for_run(shares, run, None)
    detail_explicit_zero = build_account_detail_for_run(shares, run, 0)

    assert detail_default == detail_explicit_zero
    assert detail_default != build_account_detail_for_run(shares, run, 1)


def test_build_account_detail_for_run_out_of_range_raises_with_requested_and_path_count():
    shares = compute_account_shares(_accounts())
    run = SimulationRun(
        candidate_label="test", strategy=_projection().strategy, state="FL", path_results=[_projection()],
        success_rate=1.0, percentile_bands=[], survival_adjusted_success_rate=None, figures_used=[],
    )

    with pytest.raises(PathIndexOutOfRangeError) as exc_info:
        build_account_detail_for_run(shares, run, 5)
    assert exc_info.value.requested == 5
    assert exc_info.value.path_count == 1

    with pytest.raises(PathIndexOutOfRangeError) as exc_info:
        build_account_detail_for_run(shares, run, -1)
    assert exc_info.value.requested == -1


def test_path_index_out_of_range_error_produces_422_with_documented_shape():
    exc = PathIndexOutOfRangeError(requested=5, path_count=1)
    http_exc = path_index_out_of_range_error(exc)

    assert http_exc.status_code == 422
    assert http_exc.detail == {"error": "path_index_out_of_range", "requested": 5, "path_count": 1}
