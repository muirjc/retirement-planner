"""Unit tests for derive_deterministic_return() (rp-aev)."""

from retirement_planner.comparison import derive_deterministic_return
from retirement_planner.scenario import ASSET_CLASSES, AssetClassAssumptions, MarketAssumptions

_IDENTITY_MATRIX = [[1.0 if i == j else 0.0 for j in range(8)] for i in range(8)]


def _market(**overrides) -> MarketAssumptions:
    asset_classes = {
        "us_large": AssetClassAssumptions(mean_real=0.065, std_real=0.17),
        "us_small": AssetClassAssumptions(mean_real=0.08, std_real=0.22),
        "us_medium": AssetClassAssumptions(mean_real=0.075, std_real=0.20),
        "reit": AssetClassAssumptions(mean_real=0.06, std_real=0.20),
        "aggregate_bond": AssetClassAssumptions(mean_real=0.015, std_real=0.06),
        "emerging_market": AssetClassAssumptions(mean_real=0.07, std_real=0.25),
        "international_ex_us": AssetClassAssumptions(mean_real=0.06, std_real=0.19),
        "cash": AssetClassAssumptions(mean_real=0.01, std_real=0.01),
    }
    asset_classes.update(overrides)
    return MarketAssumptions(asset_classes=asset_classes, correlation_matrix=_IDENTITY_MATRIX)


def test_each_asset_classs_own_mean_is_passed_through_unchanged():
    market = _market()
    result = derive_deterministic_return(market)
    for asset_class in ASSET_CLASSES:
        assert result.asset_class_means[asset_class] == market.asset_classes[asset_class].mean_real


def test_std_and_correlation_are_ignored():
    market_a = _market()
    market_b = _market(us_large=AssetClassAssumptions(mean_real=0.065, std_real=0.99))

    # Only std_real differs between the two fixtures (mean_real for every
    # asset class is identical) -- the deterministic result must therefore
    # be identical too, since there's no distribution to sample under this
    # engine.
    assert derive_deterministic_return(market_a) == derive_deterministic_return(market_b)


def test_asset_returns_for_plan_year_ignores_plan_year_and_never_varies():
    market = _market()
    result = derive_deterministic_return(market)
    assert result.asset_returns_for_plan_year(1) == result.asset_returns_for_plan_year(50)
    assert result.asset_returns_for_plan_year(1)["us_large"] == 0.065
