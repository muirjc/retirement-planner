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

from typing import Literal

import yaml

from .models import (
    Account,
    Household,
    HouseholdMember,
    HsaContributionPlan,
    IncomeStream,
    InheritedIraDetails,
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


def _build_income_stream(data: object, source: str, context: str) -> IncomeStream:
    """021-pension-annuity-income (rp-pid): stream_type, start_age,
    annual_amount, and inflation_adjustment are required (ScenarioParseError
    via _require() if any is missing, same discipline as every other
    required field); label and end_age are optional -- label defaults to
    ""  (display-only, never validated), end_age defaults to None (a
    lifetime stream, data-model.md).

    027-nc-bailey-exclusion: bailey_qualifying is likewise optional,
    defaulting to False -- every scenario written before this feature
    parses to the same IncomeStream it did before (contracts/scenario-
    api.md)."""
    return IncomeStream(
        label=data.get("label", "") if isinstance(data, dict) else "",
        stream_type=_require(data, "stream_type", source, context),
        start_age=_require(data, "start_age", source, context),
        annual_amount=_require(data, "annual_amount", source, context),
        inflation_adjustment=_require(data, "inflation_adjustment", source, context),
        end_age=data.get("end_age") if isinstance(data, dict) else None,
        bailey_qualifying=data.get("bailey_qualifying", False) if isinstance(data, dict) else False,
    )


def _build_household_member(data: object, source: str, context: str) -> HouseholdMember:
    ss_claim_age = _require(data, "ss_claim_age", source, context)
    # full_retirement_age (016-ss-claiming-age-actuarial-adjustment):
    # optional, defaults to this member's own ss_claim_age when omitted --
    # i.e. assume no claiming-age adjustment -- so every scenario YAML
    # written before this feature round-trips to exactly its prior
    # behavior unchanged (research.md Decision 3). A present value is read
    # as-is (float(...) accepts either a YAML int or float).
    full_retirement_age = data.get("full_retirement_age") if isinstance(data, dict) else None
    return HouseholdMember(
        person_name=_require(data, "person_name", source, context),
        current_age=_require(data, "current_age", source, context),
        ss_claim_age=ss_claim_age,
        ss_annual_benefit=_require(data, "ss_annual_benefit", source, context),
        full_retirement_age=float(full_retirement_age) if full_retirement_age is not None else float(ss_claim_age),
        # hdhp_coverage (010-advanced-tax-benefits): optional, defaults to
        # False when omitted -- every existing scenario YAML round-trips
        # unchanged.
        hdhp_coverage=data.get("hdhp_coverage", False) if isinstance(data, dict) else False,
        # predicted_death_age (017-ss-spousal-survivor-benefits): optional,
        # defaults to None when omitted -- unlike full_retirement_age,
        # None is already this field's own fully-meaningful "no
        # hypothetical death configured" value, so there is no computed
        # substitute to resolve here (mirrors hdhp_coverage's own
        # defaults-to-a-no-op-value pattern, not full_retirement_age's
        # defaults-to-a-computed-value one).
        predicted_death_age=(
            int(data["predicted_death_age"])
            if isinstance(data, dict) and data.get("predicted_death_age") is not None
            else None
        ),
        # income_streams (021-pension-annuity-income, rp-pid): optional,
        # defaults to [] when omitted -- every scenario predating this
        # feature round-trips unchanged.
        income_streams=[
            _build_income_stream(stream, source, f"{context}.income_streams[{i}]")
            for i, stream in enumerate(data.get("income_streams", []) if isinstance(data, dict) else [])
        ],
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
    # survivor_spending_reduction_pct (018-survivor-scenario-projection):
    # optional, defaults to 0.0 when omitted -- already this field's own
    # fully-meaningful "no reduction" no-op value, mirroring hdhp_coverage's
    # own defaults-to-a-no-op-value pattern (not full_retirement_age's
    # defaults-to-a-computed-value one).
    survivor_spending_reduction_pct = data.get("survivor_spending_reduction_pct", 0.0) if isinstance(data, dict) else 0.0

    return Household(
        filing_status=filing_status,
        members=members,
        survivor_spending_reduction_pct=float(survivor_spending_reduction_pct),
    )


def _build_inherited_ira_details(data: object, source: str, context: str) -> InheritedIraDetails | None:
    """012-inherited-ira-rmd: mirrors _build_roth_conversion()'s own
    optional-block pattern exactly -- absent block parses to None; a
    present block requires every one of its five fields (scenario-api.md)."""
    if data is None:
        return None
    inherited_context = f"{context}.inherited"
    return InheritedIraDetails(
        death_year=_require(data, "death_year", source, inherited_context),
        decedent_age_at_death=_require(data, "decedent_age_at_death", source, inherited_context),
        decedent_was_taking_rmds=_require(data, "decedent_was_taking_rmds", source, inherited_context),
        beneficiary_relationship=_require(data, "beneficiary_relationship", source, inherited_context),
        beneficiary_classification=_require(data, "beneficiary_classification", source, inherited_context),
    )


def _build_account(data: object, source: str, context: str, household: Household, index: int) -> Account:
    """011-per-owner-accounts: `owner` is read permissively (never
    _require()'d) -- a missing key never raises ScenarioParseError, for any
    household size; only validate() surfaces a problem for the ambiguous
    (multi-member) case. A single-member household is unambiguous, so an
    omitted owner is auto-filled from the sole member's person_name here
    (FR-003) -- no existing single-filer scenario file needs an edit.

    012-inherited-ira-rmd: `account_id` is read permissively too -- when
    omitted, it's assigned deterministically from this account's own type
    and its zero-based `index` within scenario.accounts (research.md §10),
    never a random value, so parse_scenario() stays a pure function of its
    YAML input. `inherited` is parsed by _build_inherited_ira_details()."""
    owner = data.get("owner") if isinstance(data, dict) else None
    if owner is None and len(household.members) == 1:
        owner = household.members[0].person_name
    account_type = _require(data, "account_type", source, context)
    account_id = data.get("account_id") if isinstance(data, dict) else None
    if account_id is None:
        account_id = f"{account_type}-{index}"
    inherited_data = data.get("inherited") if isinstance(data, dict) else None
    return Account(
        account_type=account_type,
        balance=_require(data, "balance", source, context),
        owner=owner,
        account_id=account_id,
        inherited=_build_inherited_ira_details(inherited_data, source, context),
    )


def _build_spending(data: object, source: str) -> SpendingProfile:
    # net_earned_income_against_spending (rp-595): optional, defaults to
    # False when omitted -- every scenario predating this feature
    # round-trips to exactly its prior behavior unchanged.
    net_earned_income = data.get("net_earned_income_against_spending", False) if isinstance(data, dict) else False
    return SpendingProfile(
        annual_need_real=_require(data, "annual_need_real", source, "spending"),
        net_earned_income_against_spending=bool(net_earned_income),
    )


def _build_roth_conversion(data: object, source: str) -> RothConversionPlan | None:
    """rp-595: window_mode/ceiling_mode/named_bracket_rate are read
    permissively (defaults reproduce every scenario predating this
    feature unchanged) -- window is _require()'d only when window_mode
    selects "explicit" (its own prior, unconditional behavior);
    bracket_ceiling_or_amount is _require()'d when ceiling_mode selects
    "dollar_amount" OR strategy is "fixed_amount" (ceiling_mode only ever
    governs the fill_to_bracket strategy's own ceiling);
    named_bracket_rate is _require()'d only when ceiling_mode selects
    "named_bracket"."""
    if data is None:
        return None
    window_mode: Literal["explicit", "auto_gap_year"] = "explicit"
    if isinstance(data, dict) and "window_mode" in data:
        window_mode = data["window_mode"]
    ceiling_mode: Literal["dollar_amount", "named_bracket"] = "dollar_amount"
    if isinstance(data, dict) and "ceiling_mode" in data:
        ceiling_mode = data["ceiling_mode"]
    strategy = _require(data, "strategy", source, "roth_conversion")

    window: tuple[int, int] | None = None
    if window_mode == "explicit":
        window_data = _require(data, "window", source, "roth_conversion")
        window = tuple(window_data)

    bracket_ceiling_or_amount: float | None = None
    if ceiling_mode == "dollar_amount" or strategy == "fixed_amount":
        bracket_ceiling_or_amount = _require(data, "bracket_ceiling_or_amount", source, "roth_conversion")

    named_bracket_rate: float | None = None
    if ceiling_mode == "named_bracket":
        named_bracket_rate = _require(data, "named_bracket_rate", source, "roth_conversion")

    return RothConversionPlan(
        strategy=strategy,
        window_mode=window_mode,
        window=window,
        ceiling_mode=ceiling_mode,
        bracket_ceiling_or_amount=bracket_ceiling_or_amount,
        named_bracket_rate=named_bracket_rate,
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

    # 011-per-owner-accounts: household is built before accounts (an
    # ordering change from this function's prior implementation) so
    # _build_account() can consult household.members for the single-member
    # owner auto-fill.
    household = _build_household(data["household"], source)

    return Scenario(
        name=scenario_name,
        household=household,
        accounts=[
            _build_account(account, source, f"accounts[{i}]", household, i)
            for i, account in enumerate(accounts_data)
        ],
        spending=_build_spending(data["spending"], source),
        state=data["state"],
        market_assumptions=_build_market_assumptions(data["market_assumptions"], source),
        simulation_settings=_build_simulation_settings(data["simulation_settings"], source),
        roth_conversion=_build_roth_conversion(data.get("roth_conversion"), source),
        hsa_contribution=_build_hsa_contribution(data.get("hsa_contribution"), source),
    )
