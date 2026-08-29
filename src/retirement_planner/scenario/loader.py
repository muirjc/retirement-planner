"""Parse raw scenario config text into a structured Scenario.

Builds the nested dataclass tree from models.py out of a YAML document,
raising ScenarioParseError (never a bare KeyError/yaml.YAMLError) for any
shape problem: malformed YAML, a missing required field, an unknown
filing_status, or a household.members count that doesn't match
filing_status. Value-level plausibility checks (negative balances,
out-of-range ages, ...) are validation.py's job, not this module's — see
FR-012 for why the two are kept separate.

See specs/001-scenario-config-management/contracts/scenario-api.md
("Errors" and "Operations" sections) for the locked public signatures of
ScenarioParseError and parse_scenario().
"""

from __future__ import annotations

import yaml

from .models import (
    Account,
    Household,
    HouseholdMember,
    HsaContributionPlan,
    MarketAssumptions,
    RothConversionPlan,
    Scenario,
    SimulationSettings,
    SpendingProfile,
)

_EXPECTED_MEMBER_COUNT = {"single": 1, "married_filing_jointly": 2}

_REQUIRED_TOP_LEVEL_FIELDS = (
    "household",
    "accounts",
    "spending",
    "state",
    "market_assumptions",
    "simulation_settings",
)

_MARKET_ASSUMPTION_FIELDS = (
    "equity_allocation",
    "equity_return_mean_real",
    "equity_return_std_real",
    "bond_allocation",
    "bond_return_mean_real",
    "bond_return_std_real",
    "correlation",
)


class ScenarioParseError(Exception):
    """Raised when a config file cannot be parsed into a Scenario shape at all
    (malformed YAML, wrong household member count for filing_status, wrong
    types, or a missing required field). Distinct from a value-level
    validation problem — see FR-012.
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"{source}: {reason}")


def _require(data: object, field_name: str, source: str, context: str = ""):
    path = f"{context}.{field_name}" if context else field_name
    if not isinstance(data, dict):
        raise ScenarioParseError(source, f"expected a mapping at '{context or '<root>'}'")
    if field_name not in data or data[field_name] is None:
        raise ScenarioParseError(source, f"missing required field '{path}'")
    return data[field_name]


def _build_household_member(data: object, source: str, context: str) -> HouseholdMember:
    return HouseholdMember(
        person_name=_require(data, "person_name", source, context),
        current_age=_require(data, "current_age", source, context),
        ss_claim_age=_require(data, "ss_claim_age", source, context),
        ss_annual_benefit=_require(data, "ss_annual_benefit", source, context),
        # hdhp_coverage (010-advanced-tax-benefits): optional, defaults to
        # False when omitted -- every existing scenario YAML round-trips
        # unchanged.
        hdhp_coverage=data.get("hdhp_coverage", False) if isinstance(data, dict) else False,
    )


def _build_household(data: object, source: str) -> Household:
    filing_status = _require(data, "filing_status", source, "household")
    members_data = _require(data, "members", source, "household")

    if filing_status not in _EXPECTED_MEMBER_COUNT:
        raise ScenarioParseError(source, f"unknown filing_status '{filing_status}'")

    members = [
        _build_household_member(member, source, f"household.members[{i}]")
        for i, member in enumerate(members_data)
    ]

    expected = _EXPECTED_MEMBER_COUNT[filing_status]
    if len(members) != expected:
        raise ScenarioParseError(
            source,
            f"household.members has {len(members)} member(s) but filing_status "
            f"'{filing_status}' requires {expected}",
        )
    return Household(filing_status=filing_status, members=members)


def _build_account(data: object, source: str, context: str) -> Account:
    return Account(
        account_type=_require(data, "account_type", source, context),
        balance=_require(data, "balance", source, context),
    )


def _build_spending(data: object, source: str) -> SpendingProfile:
    return SpendingProfile(annual_need_real=_require(data, "annual_need_real", source, "spending"))


def _build_roth_conversion(data: object, source: str) -> RothConversionPlan | None:
    if data is None:
        return None
    window = _require(data, "window", source, "roth_conversion")
    return RothConversionPlan(
        strategy=_require(data, "strategy", source, "roth_conversion"),
        bracket_ceiling_or_amount=_require(data, "bracket_ceiling_or_amount", source, "roth_conversion"),
        window=tuple(window),
    )


def _build_hsa_contribution(data: object, source: str) -> HsaContributionPlan | None:
    """010-advanced-tax-benefits: mirrors _build_roth_conversion()'s own
    optional-block pattern exactly."""
    if data is None:
        return None
    return HsaContributionPlan(
        annual_amount=_require(data, "annual_amount", source, "hsa_contribution"),
    )


def _build_market_assumptions(data: object, source: str) -> MarketAssumptions:
    values = {f: _require(data, f, source, "market_assumptions") for f in _MARKET_ASSUMPTION_FIELDS}
    return MarketAssumptions(**values)


def _build_simulation_settings(data: object, source: str) -> SimulationSettings:
    return SimulationSettings(
        n_paths=_require(data, "n_paths", source, "simulation_settings"),
        seed=_require(data, "seed", source, "simulation_settings"),
        plan_to_age=_require(data, "plan_to_age", source, "simulation_settings"),
    )


def parse_scenario(yaml_text: str, *, name: str | None = None) -> Scenario:
    """Parse raw YAML text into a Scenario. Does NOT run validate() — callers
    combine parse + validate themselves, or use store.load_scenario(), which
    does both. Raises ScenarioParseError on malformed input.
    """
    source = name or "<scenario>"
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ScenarioParseError(source, f"invalid YAML syntax: {exc}") from exc

    if not isinstance(data, dict):
        raise ScenarioParseError(source, "config must be a YAML mapping at the top level")

    for field_name in _REQUIRED_TOP_LEVEL_FIELDS:
        _require(data, field_name, source)

    scenario_name = name or data.get("name")
    if not scenario_name:
        raise ScenarioParseError(source, "missing required field 'name'")

    accounts_data = data["accounts"]
    if not accounts_data:
        raise ScenarioParseError(source, "accounts must contain at least one entry")

    return Scenario(
        name=scenario_name,
        household=_build_household(data["household"], source),
        accounts=[
            _build_account(account, source, f"accounts[{i}]")
            for i, account in enumerate(accounts_data)
        ],
        spending=_build_spending(data["spending"], source),
        state=data["state"],
        market_assumptions=_build_market_assumptions(data["market_assumptions"], source),
        simulation_settings=_build_simulation_settings(data["simulation_settings"], source),
        roth_conversion=_build_roth_conversion(data.get("roth_conversion"), source),
        hsa_contribution=_build_hsa_contribution(data.get("hsa_contribution"), source),
    )
