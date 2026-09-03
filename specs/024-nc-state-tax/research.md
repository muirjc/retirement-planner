# Research: North Carolina State Income Tax Module

## 1. NC is a true flat-rate state — one bracket row, not a table

**Decision**: Represent NC's rate as a `SourcedFigure` of `BracketRow` tuples with **exactly one row per tax year** — `(BracketRow(rate=R, income_up_to=None),)` — run through the existing `apply_progressive_brackets()`, per the bead's own design note.

**Rationale**: Unlike SC (a genuine 3-bracket graduated table, including a $0-rate bottom bracket) or DE (a genuine 6-bracket table), North Carolina has taxed 100% of taxable income at a single statutory rate since the 2013 tax reform (effective tax year 2014) — there is no $0-rate floor bracket and no higher bracket at any income level. `apply_progressive_brackets()` degenerates correctly for a single unbounded row (confirmed by inspection of `tax/bracket_math.py`: it walks the row list, accumulating `rate * min(remaining, row width)`, so a single `income_up_to=None` row just returns `income * rate`) — no separate flat-rate helper is needed, keeping every state module homogeneous as the bead's design note prefers.

**Alternatives considered**: *A dedicated `apply_flat_rate()` helper, matching `fl.py`'s "no bracket table at all" precedent.* Rejected — FL's precedent is for **zero** tax (no figure consulted at all), a structurally different case from NC's **one, real, nonzero** rate. NC's case is exactly what `apply_progressive_brackets()` with a single row is for; introducing a second code path would be the extra complexity the design note explicitly says to avoid absent a real modeling gap, and there is none here.

## 2. The current, legislated rate schedule

**Decision**: `_2025_BRACKETS = (BracketRow(rate=0.0425, income_up_to=None),)`; `_2026_BRACKETS = (BracketRow(rate=0.0399, income_up_to=None),)`. The `SourcedFigure`'s `schedule` dict maps every documented year before 2026 to `_2025_BRACKETS`... actually: years *up to and including 2024* have no real bearing on this feature (the engine's practical horizon starts at "now"), so — mirroring `sc.py`'s own "hold the pre-step table for years before the step, hold the post-step table for the step year onward" pattern exactly — the schedule maps every year in `_DOCUMENTED_YEARS.start..2025` (inclusive) to `_2025_BRACKETS` and every year `2026..`(`_DOCUMENTED_YEARS.stop`) to `_2026_BRACKETS`.

**Rationale**: Confirmed against NCDOR's own "Tax Rate Schedules" page (primary/authoritative source, fetched 2026-09-03): "Tax Year 2025: The rate is 4.25% (0.0425)" and "Tax Year 2026 and Later: The rate is 3.99% (0.0399)," both flat rates with no brackets, enacted by Session Law 2023-134 amending N.C. Gen. Stat. §105-153.7. This is a real, already-legislated step (unlike SC's illustrative 2026→2027 step), so — per constitution Principle III's verified-figure gate — this figure ships `verified=True`, not `verified=False` like SC's/DE's inherited placeholders.

**On years beyond 2026**: NCDOR's own page notes "additional rate changes may apply to tax years beginning with 2027 based on certain rate reduction triggers" (revenue-trigger-conditioned, not yet a fixed legislated number). Per the project's existing convention (`sc.py`, `de.py`, `tax/federal.py`: hold the last documented figure flat across the rest of `_DOCUMENTED_YEARS` rather than leaving later years unsupported), 3.99% is held flat for tax year 2026 through the end of the documented horizon. This is not fabricating a number — it is the same "no further change is currently legislated, so none is modeled" posture the rest of the engine already takes, and the module docstring will say so explicitly (Principle I).

**Citations** (confirmed 2026-09-03, `verified=True`):
- NCDOR, "Tax Rate Schedules," https://www.ncdor.gov/taxes-forms/individual-income-tax/tax-rate-schedules (states both the 2025 4.25% and 2026+ 3.99% flat rates directly, and that NC's tax has no brackets).
- N.C. Gen. Stat. §105-153.7, as amended by Session Law 2023-134 (the underlying statute NCDOR's page cites for the schedule).

## 3. No exclusion `SourcedFigure` — the Bailey settlement doesn't fit `IncomeComponents`

**Decision**: `nc.py` introduces no analogue to SC's `_AGE_65_EXCLUSION` / DE's `_AGE_60_EXCLUSION`. NC's `compute_tax()` taxes 100% of `income.ordinary_income` at the flat rate, full stop.

**Rationale — what NC's actual law provides**: NC has no general age-based retirement-income exclusion. What it has instead:
- **The Bailey settlement** (*Bailey v. State of North Carolina*, 1998; N.C. Gen. Stat. §105-134.6 history): fully exempts retirement benefits from qualifying government defined-benefit plans (NC/local Teachers' and State Employees' Retirement System, Local Governmental Employees' Retirement System, U.S. government, including military) or state §401(k)/§457 plans, **only** for a retiree who had five or more years of creditable service, or contributed to the plan, as of **August 12, 1989**. It explicitly does *not* cover other states' government retirement plans. (Confirmed against NCDOR, "Bailey Decision Concerning Federal, State and Local Retirement Benefits," and current Form D-400 Schedule S 2025, Line 9.)
- **A separate, newer military retirement exemption** (S.L. 2021-180, effective tax year 2021+): exempts qualifying military retirement pay regardless of the 1989 vesting cutoff — a second, independent source-of-income-based carve-out, not an age rule either.
- **No evidence of a surviving general non-Bailey retirement-benefit deduction**: the historical $4,000 (single) / $8,000 (MFJ) deduction once codified at G.S. §105-134.6(b)(6) does not appear on the current 2025 Schedule S's deductions-from-federal-AGI section (only the Bailey-qualified-benefits line, Line 9, is present) — consistent with it having been eliminated in NC's 2013 flat-tax/enlarged-standard-deduction reform, though no single source was found stating the repeal explicitly. Not being coded, either way, for the reason below.

Every one of these carve-outs keys off **income source** (which pension plan the money came from) and, for Bailey, a **pre-1989 vesting date fact** — neither is present in `IncomeComponents`, which carries a single blended `ordinary_income` figure with no per-source breakdown (confirmed: `comparison/projection.py`'s `IncomeComponents(ordinary_income=mechanics_result.ordinary_income, ...)` construction already merges withdrawals, RMDs, pension, and wage income into one number before any state module ever sees it). Adding that breakdown would mean changing `comparison/`/`simulation/`'s income-assembly logic and `IncomeComponents` itself — a shared model every other state module also depends on — which is outside this bead's explicit scope boundary.

**Alternatives considered**:
- *Approximate Bailey with an age-based exclusion, reusing SC's/DE's shape.* Rejected outright — the bead's own acceptance criteria warns explicitly against this, and it would be actively wrong: a 70-year-old NC retiree living on a private 401(k) or an out-of-state pension owes full NC tax on that income under real law, while a 55-year-old NC retiree drawing a pre-1989-vested state pension owes none — age predicts neither case correctly.
- *Extend `IncomeComponents` with a `government_pension_income` field.* Rejected for this feature — it would touch `comparison/projection.py`'s income assembly (explicitly out of scope) and every other state module's contract, for a feature whose stated boundary is "one new module, one registry entry." Left as a natural, explicitly-named candidate for separate follow-on work if a future feature needs source-attributed pension income for other reasons too (e.g., a different state's rules).

## 4. Social Security stays untaxed, same shape as SC/DE

**Decision**: `compute_tax()` reads only `income.ordinary_income`; `income.social_security_gross_benefit` is never referenced, identical to `sc.py`/`de.py`.

**Rationale**: Confirmed against NCDOR, "Social Security and Railroad Retirement Benefits": North Carolina fully exempts Social Security retirement, disability, and survivor benefits from state income tax, unconditionally (no age or income threshold) — the same "doesn't tax Social Security, so it never entered the taxable base to begin with" shape SC's and DE's docstrings already describe, not a new exclusion figure to cite.

## 5. No BFF, comparison, simulation, or UI change needed

**Decision**: Confirmed by reading `services/bff/src/rp_bff/routes/reference.py` — it already serves `list(STATE_MODULES.keys())` (or equivalent) directly, with no per-state branch. Adding `"NC"` to `STATE_MODULES` is sufficient; the route requires no edit, only a test asserting `"NC"` now appears in its response.

**Rationale**: This is exactly constitution Principle IV's promise (state modules are added without touching consumers) — the same reason SC→DE→FL never required BFF/UI changes either.
