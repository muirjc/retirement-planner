"""Named-scenario storage: one YAML file per scenario under config/scenarios/.

Each scenario name maps to its own file, so saving or editing one scenario
can never touch another's data (FR-005) and saving to an existing name
overwrites it (FR-015). load_scenario() combines loader.parse_scenario()
with validation.validate() so a caller gets a fully validated Scenario back
in one call.

See specs/001-scenario-config-management/contracts/scenario-api.md
("Operations" section) for the locked public signatures of save_scenario(),
list_scenarios(), and load_scenario().
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .loader import ScenarioParseError, parse_scenario
from .models import Scenario
from .validation import validate

DEFAULT_SCENARIOS_DIR = Path("config/scenarios")

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _resolve_dir(scenarios_dir: Path | None) -> Path:
    return scenarios_dir if scenarios_dir is not None else DEFAULT_SCENARIOS_DIR


def _sanitize_filename(name: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub("_", name)


def _path_for(name: str, scenarios_dir: Path) -> Path:
    return scenarios_dir / f"{_sanitize_filename(name)}.yaml"


def _scenario_to_dict(scenario: Scenario) -> dict:
    data: dict = {
        "name": scenario.name,
        "household": {
            "filing_status": scenario.household.filing_status,
            "members": [
                {
                    "person_name": member.person_name,
                    "current_age": member.current_age,
                    "ss_claim_age": member.ss_claim_age,
                    "ss_annual_benefit": member.ss_annual_benefit,
                    "hdhp_coverage": member.hdhp_coverage,  # 010-advanced-tax-benefits
                }
                for member in scenario.household.members
            ],
        },
        "accounts": [
            # 011-per-owner-accounts: owner must round-trip through save/load
            # like every other Account field -- found missing here via the
            # same class of save/load round-trip gap 010's hdhp_coverage/
            # hsa_contribution fields hit (see hsa_contribution note below).
            {"account_type": account.account_type, "balance": account.balance, "owner": account.owner}
            for account in scenario.accounts
        ],
        "spending": {"annual_need_real": scenario.spending.annual_need_real},
        "state": scenario.state,
        "market_assumptions": {
            "equity_allocation": scenario.market_assumptions.equity_allocation,
            "equity_return_mean_real": scenario.market_assumptions.equity_return_mean_real,
            "equity_return_std_real": scenario.market_assumptions.equity_return_std_real,
            "bond_allocation": scenario.market_assumptions.bond_allocation,
            "bond_return_mean_real": scenario.market_assumptions.bond_return_mean_real,
            "bond_return_std_real": scenario.market_assumptions.bond_return_std_real,
            "correlation": scenario.market_assumptions.correlation,
        },
        "simulation_settings": {
            "n_paths": scenario.simulation_settings.n_paths,
            "seed": scenario.simulation_settings.seed,
            "plan_to_age": scenario.simulation_settings.plan_to_age,
        },
    }
    if scenario.roth_conversion is not None:
        data["roth_conversion"] = {
            "strategy": scenario.roth_conversion.strategy,
            "bracket_ceiling_or_amount": scenario.roth_conversion.bracket_ceiling_or_amount,
            "window": list(scenario.roth_conversion.window),
        }
    if scenario.hsa_contribution is not None:
        # 010-advanced-tax-benefits: found missing here (and on
        # HouseholdMember.hdhp_coverage above) via a real BFF round-trip
        # regression test -- this function builds its dict field-by-field
        # rather than generically, the same class of gap loader.py's own
        # _build_household_member()/parse_scenario() already had to be
        # extended for on the read side.
        data["hsa_contribution"] = {"annual_amount": scenario.hsa_contribution.annual_amount}
    return data


def save_scenario(scenario: Scenario, *, scenarios_dir: Path | None = None) -> None:
    """Persist `scenario` under `scenario.name`, overwriting any existing
    saved scenario of the same name (FR-015). Does not require the scenario
    to be valid — an author may save a work-in-progress scenario with
    blocking flags and come back to fix it later.
    """
    directory = _resolve_dir(scenarios_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = _path_for(scenario.name, directory)
    path.write_text(yaml.safe_dump(_scenario_to_dict(scenario), sort_keys=False))


def list_scenarios(*, scenarios_dir: Path | None = None) -> list[str]:
    """Return every saved scenario name (FR-004), in a stable, alphabetical
    order.
    """
    directory = _resolve_dir(scenarios_dir)
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.yaml"))


def delete_scenario(name: str, *, scenarios_dir: Path | None = None) -> None:
    """Removes the named scenario's saved file. Raises ScenarioParseError
    (the same exception type and message shape load_scenario() already
    raises for a missing scenario) if no file exists for `name` -- added
    for 007-bff-api-service (research.md §1), so a client can remove a
    saved scenario over HTTP; not part of 001's original locked contract.
    """
    directory = _resolve_dir(scenarios_dir)
    path = _path_for(name, directory)
    if not path.exists():
        raise ScenarioParseError(name, f"no saved scenario named '{name}'")
    path.unlink()


def load_scenario(name: str, *, scenarios_dir: Path | None = None) -> Scenario:
    """Load the named scenario, parse it, and populate its validation_flags
    (i.e., loader.parse_scenario() + validation.validate() combined). Raises
    ScenarioParseError if the named scenario's file doesn't exist or can't be
    parsed. Never raises merely because of a blocking ValidationFlag — only
    a ScenarioParseError blocks the call itself, per FR-012 vs FR-006/FR-014.
    """
    directory = _resolve_dir(scenarios_dir)
    path = _path_for(name, directory)
    if not path.exists():
        raise ScenarioParseError(name, f"no saved scenario named '{name}'")

    scenario = parse_scenario(path.read_text(), name=name)
    scenario.validation_flags = validate(scenario)
    return scenario
