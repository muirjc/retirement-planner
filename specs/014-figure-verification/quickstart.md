# Quickstart: Figure Verification (Placeholder Tax Figures)

Validates each of the 4 user stories end-to-end: statutory figures
re-cited with no computed-output change (US1, SC-002), annually-published
figures re-cited and corrected (US2, SC-002), the RMD start age's 2033
step actually applied (US3, SC-003), and the Uniform Lifetime Table
covering ages beyond 100 (US4, SC-004).

Every specific dollar/divisor value below depends on what an
implementation task's own primary-source lookup finds (research.md §1-2)
— this guide checks the *relationships* FR-001-FR-009 require (verified
flags flip, citations name a real source, a schedule actually varies, a
lookup that used to fail now succeeds), not hardcoded expected figures.

## Prerequisites

- Python 3.11+, same environment as `001`-`013` (no new dependency).
- No config files, no network access needed to *run* this guide — the
  network access happened once, earlier, during each figure's own
  implementation research (research.md §1).

## 1. Statutory figures verified, computed output unchanged (User Story 1)

```python
from retirement_planner.tax.niit import _NIIT_RATE, _NIIT_THRESHOLDS, compute_niit
from retirement_planner.tax.social_security import _THRESHOLDS, compute_taxable_social_security
from retirement_planner.tax.models import IncomeComponents

# Every Group A figure is marked verified, with a citation naming a real
# statute subsection -- not "placeholder" or "pending verification" text.
for figure in [_NIIT_RATE, *_NIIT_THRESHOLDS.values(), *_THRESHOLDS.values()]:
    assert figure.verified is True
    assert "placeholder" not in figure.citation.lower()
    assert "pending verification" not in figure.citation.lower()

# Computed output is unchanged from before this feature: these figures'
# underlying numbers were already correct, only their sourcing was
# unconfirmed (spec.md User Story 1).
income = IncomeComponents(ordinary_income=280_000, social_security_gross_benefit=30_000)
taxable_ss, _ = compute_taxable_social_security(income, "married_filing_jointly", 2026)
# 85% is the statutory ceiling this figure's threshold pair drives toward
# at high provisional income -- unchanged by this feature's re-citation.
assert taxable_ss == income.social_security_gross_benefit * 0.85

niit_result = compute_niit(magi=280_000, investment_income=40_000, filing_status="married_filing_jointly", tax_year=2026)
assert niit_result.threshold_exceeded is True  # $280k MAGI > $250k MFJ threshold
assert niit_result.surtax_owed == min(40_000, 280_000 - 250_000) * 0.038
```

## 2. Annually-published figures verified and corrected (User Story 2)

```python
from retirement_planner.tax.federal import _FEDERAL_BRACKETS
from retirement_planner.tax.irmaa import _IRMAA_TIERS
from retirement_planner.mechanics.hsa import _HSA_LIMITS

for figure in [*_FEDERAL_BRACKETS.values(), *_IRMAA_TIERS.values(), _HSA_LIMITS]:
    assert figure.verified is True
    # Citation names a specific year and publication, not a placeholder.
    assert "placeholder" not in figure.citation.lower()
    assert "illustrative" not in figure.citation.lower()
    assert any(char.isdigit() for char in figure.citation)  # names a year
```

## 3. RMD start age's 2033 step is applied (User Story 3, SC-003)

```python
from retirement_planner.mechanics.rmd import RMD_START_AGE, compute_rmd

assert RMD_START_AGE.verified is True

# The schedule itself steps at 2033.
assert RMD_START_AGE.value_for_year(2032) == 73
assert RMD_START_AGE.value_for_year(2033) == 75

# A 73-year-old owes an RMD before 2033 (today's start age) but not once
# the 2033+ start age (75) applies -- confirms the schedule actually
# drives compute_rmd()'s own start-age gate, not just the raw
# SourcedFigure lookup above.
assert compute_rmd(traditional_balance=500_000, member_age=73, tax_year=2032).required_amount > 0.0
assert compute_rmd(traditional_balance=500_000, member_age=73, tax_year=2033).required_amount == 0.0
```

## 4. Uniform Lifetime Table covers ages beyond 100 (User Story 4, SC-004)

```python
from retirement_planner.mechanics.rmd import UNIFORM_LIFETIME_TABLE, compute_rmd

assert UNIFORM_LIFETIME_TABLE.verified is True

# Before this feature, age 101 wasn't in _UNIFORM_LIFETIME_DIVISORS at
# all -- this lookup raised a plain KeyError (data-model.md). After, it
# succeeds and returns a real, cited divisor.
result = compute_rmd(traditional_balance=500_000, member_age=101, tax_year=2026)
assert result.divisor is not None
assert result.required_amount == 500_000 / result.divisor
```

## 5. Regression check: existing suite still passes, with intended diffs traceable (SC-005)

```bash
pytest
```

Any test whose expected value changed as a direct result of a Group B/C
correction (Constraints, plan.md) should have its diff traceable to the
specific figure that changed — e.g. a comment or commit note pointing at
the corrected `federal_brackets_mfj` threshold, not an unexplained
fixture edit.
