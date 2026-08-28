"""Unit tests for src/rp_ui/errors.py -- T003.

Confirms each exception type carries exactly the attributes data-model.md
§ Error types documents, so a page script can build a specific message
from structured data rather than string-matching a response body.
"""

from rp_ui.errors import (
    BackendUnreachableError,
    BlockingValidationError,
    CostBudgetExceededError,
    InvalidScenarioError,
    RpUiError,
    ScenarioNotFoundError,
    UnexpectedBackendError,
    UnknownReferenceValueError,
    UnsupportedTaxYearError,
)


def test_scenario_not_found_error_carries_name():
    err = ScenarioNotFoundError(name="base_case")
    assert err.name == "base_case"
    assert "base_case" in str(err)


def test_invalid_scenario_error_carries_reason():
    err = InvalidScenarioError(reason="accounts[0].balance must be >= 0")
    assert err.reason == "accounts[0].balance must be >= 0"


def test_blocking_validation_error_carries_flags():
    flags = [{"field": "accounts[0].balance", "message": "must be >= 0", "severity": "blocking"}]
    err = BlockingValidationError(flags=flags)
    assert err.flags == flags


def test_unknown_reference_value_error_carries_field_and_value():
    err = UnknownReferenceValueError(field="state", value="ZZ")
    assert err.field == "state"
    assert err.value == "ZZ"


def test_cost_budget_exceeded_error_carries_estimate_and_budget():
    err = CostBudgetExceededError(estimated_seconds=180.0, budget_seconds=30.0)
    assert err.estimated_seconds == 180.0
    assert err.budget_seconds == 30.0


def test_unsupported_tax_year_error_carries_figure_and_year_details():
    err = UnsupportedTaxYearError(figure_name="rmd_start_age", requested_year=1900, documented_years=[2020, 2026])
    assert err.figure_name == "rmd_start_age"
    assert err.requested_year == 1900
    assert err.documented_years == [2020, 2026]


def test_backend_unreachable_error_carries_underlying_exception():
    underlying = ConnectionError("refused")
    err = BackendUnreachableError(underlying=underlying)
    assert err.underlying is underlying


def test_unexpected_backend_error_carries_status_code_and_body():
    err = UnexpectedBackendError(status_code=500, body="internal server error")
    assert err.status_code == 500
    assert err.body == "internal server error"


def test_every_error_type_is_an_rp_ui_error():
    assert issubclass(ScenarioNotFoundError, RpUiError)
    assert issubclass(InvalidScenarioError, RpUiError)
    assert issubclass(BlockingValidationError, RpUiError)
    assert issubclass(UnknownReferenceValueError, RpUiError)
    assert issubclass(UnsupportedTaxYearError, RpUiError)
    assert issubclass(CostBudgetExceededError, RpUiError)
    assert issubclass(BackendUnreachableError, RpUiError)
    assert issubclass(UnexpectedBackendError, RpUiError)
