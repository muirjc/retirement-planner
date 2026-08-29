"""Value-level validation rules for a parsed Scenario.

Every rule here follows FR-006: validate() always runs every rule to
completion and returns every problem found, never stopping at the first one.
Rule details (which fields, thresholds, and severities) are documented in
specs/001-scenario-config-management/data-model.md; the locked public
signature of validate() is in
specs/001-scenario-config-management/contracts/scenario-api.md
("Operations" section).
"""

from __future__ import annotations

from .models import Scenario, ValidationFlag


def validate(scenario: Scenario) -> list[ValidationFlag]:
    """Run every validation rule against `scenario` and return every problem
    found (FR-006) — never stops at the first one. Does not mutate
    `scenario`.
    """
    flags: list[ValidationFlag] = []
    flags.extend(_validate_accounts(scenario))
    flags.extend(_validate_household(scenario))
    flags.extend(_validate_spending(scenario))
    return flags


def _validate_accounts(scenario: Scenario) -> list[ValidationFlag]:
    flags = []
    member_names = [member.person_name for member in scenario.household.members]
    for index, account in enumerate(scenario.accounts):
        if account.balance < 0:
            flags.append(
                ValidationFlag(
                    field=f"accounts[{account.account_type}].balance",
                    message=(
                        f"Account balance is negative (${account.balance:,.2f}); "
                        "balances cannot be negative."
                    ),
                    severity="blocking",
                )
            )
        # 011-per-owner-accounts: checked here, not just relied on from
        # parse_scenario()'s own auto-fill, so a Scenario built directly
        # (bypassing the loader, as most of this codebase's own test
        # fixtures do) is validated identically (data-model.md § Account).
        if account.owner is None:
            if len(member_names) > 1:
                flags.append(
                    ValidationFlag(
                        field=f"accounts[{index}].owner",
                        message=(
                            "Account is missing an owner — choose one of: "
                            f"{', '.join(member_names)}"
                        ),
                        severity="blocking",
                    )
                )
            # A single-member household is unambiguous (FR-003) -- never
            # flagged, regardless of how the Scenario was constructed.
        elif account.owner not in member_names:
            flags.append(
                ValidationFlag(
                    field=f"accounts[{index}].owner",
                    message=(
                        f"Account owner '{account.owner}' does not match any household "
                        f"member — known members: {', '.join(member_names)}"
                    ),
                    severity="blocking",
                )
            )
        # 012-inherited-ira-rmd (data-model.md § Validation rules): three
        # independent checks, each firing on its own -- an inherited
        # account can fail more than one at once (e.g. wrong account_type
        # AND an unsupported beneficiary_classification), and every
        # problem is reported, not just the first (FR-006, 001).
        if account.inherited is not None:
            if account.inherited.decedent_was_taking_rmds is False:
                flags.append(
                    ValidationFlag(
                        field=f"accounts[{index}].inherited",
                        message=(
                            "This inherited account's original owner had not yet begun "
                            "required distributions before death (\"pre-RBD\") — this case "
                            "is not yet supported."
                        ),
                        severity="blocking",
                    )
                )
            if account.inherited.beneficiary_classification != "non_eligible_designated_beneficiary":
                flags.append(
                    ValidationFlag(
                        field=f"accounts[{index}].inherited",
                        message=(
                            "This inherited account's beneficiary is classified as "
                            f"'{account.inherited.beneficiary_classification}' — eligible "
                            "designated beneficiary cases are not yet supported."
                        ),
                        severity="blocking",
                    )
                )
            if account.account_type != "traditional":
                flags.append(
                    ValidationFlag(
                        field=f"accounts[{index}].inherited",
                        message=(
                            f"This inherited account is '{account.account_type}' — only "
                            "inherited traditional accounts are supported."
                        ),
                        severity="blocking",
                    )
                )
    return flags


def _validate_household(scenario: Scenario) -> list[ValidationFlag]:
    flags = []
    for index, member in enumerate(scenario.household.members):
        if not (62 <= member.ss_claim_age <= 70):
            flags.append(
                ValidationFlag(
                    field=f"household.members[{index}].ss_claim_age",
                    message=(
                        f"Social Security claiming age {member.ss_claim_age} is outside "
                        "the allowed range of 62-70."
                    ),
                    severity="blocking",
                )
            )
        if member.ss_annual_benefit < 0:
            flags.append(
                ValidationFlag(
                    field=f"household.members[{index}].ss_annual_benefit",
                    message=(
                        "Social Security annual benefit is negative "
                        f"(${member.ss_annual_benefit:,.2f}); it cannot be negative."
                    ),
                    severity="blocking",
                )
            )
    return flags


def _validate_spending(scenario: Scenario) -> list[ValidationFlag]:
    flags: list[ValidationFlag] = []
    spending = scenario.spending.annual_need_real

    if spending < 0:
        flags.append(
            ValidationFlag(
                field="spending.annual_need_real",
                message=(
                    f"Annual spending need is negative (${spending:,.2f}); "
                    "it cannot be negative."
                ),
                severity="blocking",
            )
        )
        # An already-impossible spending value isn't a plausibility question.
        return flags

    if not scenario.household.members:
        return flags

    older_current_age = max(member.current_age for member in scenario.household.members)
    horizon_years = scenario.simulation_settings.plan_to_age - older_current_age
    total_assets = sum(account.balance for account in scenario.accounts)

    if horizon_years > 0 and spending * horizon_years > total_assets:
        flags.append(
            ValidationFlag(
                field="spending.annual_need_real",
                message=(
                    f"Planned annual spending (${spending:,.2f}) over a "
                    f"{horizon_years}-year horizon (${spending * horizon_years:,.2f} total) "
                    f"exceeds total starting assets (${total_assets:,.2f}), with no other "
                    "income sources accounted for. This may be optimistic — double-check "
                    "before relying on this scenario."
                ),
                severity="warning",
            )
        )
    return flags
