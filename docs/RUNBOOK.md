# Runbook: Retirement Planner

**Status**: Living document — reflects the codebase as of `specs/001`–`023`

> **Keeping this document current**: this runbook describes how to
> actually operate the system `docs/SOLUTION_ARCHITECTURE.md` describes
> and `docs/BRD.md` specifies — start/stop procedure, health checks,
> data handling, and troubleshooting. A feature that changes a port, an
> environment variable, an install command, a CI gate, or a failure mode
> worth knowing about **must** update the relevant section here in the
> same change, the same discipline the other two docs ask for. If a
> command here doesn't work, the command is stale — fix this document,
> don't route around it.

---

## 0. Scope

This is **not** a production operations runbook for a hosted service —
per `docs/SOLUTION_ARCHITECTURE.md` §10, there is no hosted deployment:
the BFF and UI are two local processes on one developer/household
machine, bound to `127.0.0.1`, with no container, orchestrator, or
external database. This document instead covers the thing that *is*
operationally real for a tool like that: getting the stack up, confirming
it's healthy, not losing the one piece of persisted state
(`config/scenarios/*.yaml`), and diagnosing the failures that actually
happen in practice.

If you're deploying this to somewhere other than a single trusted local
machine, stop and reread `docs/BRD.md` §2.2 (non-goals) and
`docs/SOLUTION_ARCHITECTURE.md` §1 (deployment posture) first — that's a
scope change, not an ops question this runbook answers.

## 1. Prerequisites

- Python 3.11+ (this repo's own dev environment uses a `.venv` with
  Python 3.14 as `.venv/bin/python`, plus a parallel Python 3.12
  interpreter at `.venv/bin/python3.12` used only for the e2e/Playwright
  suite — see §6 if you hit interpreter-mismatch errors).
- `git`.
- No network access needed at runtime (offline-first, per the
  constitution) — only for the one-time `pip install` steps below and,
  optionally, `bd`/CI tooling.

## 2. First-time setup

```bash
# From the repo root
pip install -e ".[dev]"                     # core library
pip install -e "services/bff[dev]"          # BFF (depends on the core library above)
pip install -e "apps/streamlit_ui[dev]"     # Streamlit UI
```

Install order matters: `services/bff` and `apps/streamlit_ui` both
declare `retirement_planner` as a dependency but expect it already
present as a sibling editable install (see each package's own
`pyproject.toml` comment) — the core library must land first, as above.

Optional, only needed for the e2e suite or the `run-retirement-planner`
skill's `smoke` subcommand (§4):

```bash
cd e2e && ../.venv/bin/python3.12 -m pip install -e ".[dev]" \
       && ../.venv/bin/python3.12 -m playwright install chromium && cd ..
```

## 3. Starting and stopping the stack

Two independent processes, in two terminals:

```bash
# Terminal 1 — the API, bound to 127.0.0.1 only (never a public interface)
uvicorn rp_bff.main:app --app-dir services/bff/src --host 127.0.0.1 --port 8000

# Terminal 2 — the UI, pointed at that API
RP_BFF_BASE_URL=http://127.0.0.1:8000/api/v1 streamlit run apps/streamlit_ui/app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`). The
BFF's interactive API docs are at `http://127.0.0.1:8000/docs`.

**Stopping**: Ctrl-C each terminal. Neither process holds any state
outside `config/scenarios/*.yaml` (§5) or an in-memory request, so there
is no drain/quiesce step — a hard stop is always safe.

**If `uvicorn`/`streamlit` aren't on `PATH`, or fail with
`ModuleNotFoundError: No module named 'retirement_planner'`**: invoke via
`python -m uvicorn ...` / `python -m streamlit run ...` using the
interpreter you actually installed the three packages into, instead of
the bare entry-point scripts — see §6's first troubleshooting entry for
why this happens in some dev environments.

### Agent / scripted path

`.claude/skills/run-retirement-planner/driver.py` wraps the same startup
sequence for automated use (reuses `e2e/conftest.py`'s own tested
launch/readiness helpers), on an isolated temp scenarios directory —
never the real `config/scenarios/`:

```bash
# Launch, screenshot home + Scenarios pages, check for console errors, tear down
.venv/bin/python3.12 .claude/skills/run-retirement-planner/driver.py smoke

# Launch and block until Ctrl-C, for manual poking
.venv/bin/python3.12 .claude/skills/run-retirement-planner/driver.py start [--bff-port N] [--ui-port N]
```

## 4. Health checks

The BFF has no dedicated `/health` route; the CI pipeline's own liveness
check (`.github/workflows/ci.yml`, ZAP job) is the reference/comparison
route, and it doubles as a smoke test here:

```bash
curl -f http://127.0.0.1:8000/api/v1/reference/states
```

A `200` with a JSON list of state codes (`FL`, `SC`, `DE` today) means
the BFF is up and the core library imported cleanly. `http://127.0.0.1:8000/docs`
returning FastAPI's Swagger UI is the same check, visually.

For the UI, a `200` on `http://localhost:8501` plus no red Streamlit
exception banner on first load is the equivalent check; the UI has no
separate API to probe — it fails loudly in-page if the BFF isn't
reachable (check `RP_BFF_BASE_URL` first, per §6).

For a full stack check exercising real user flows (create a scenario,
run a simulation, compare candidates) through a real browser, run the
`smoke` subcommand in §3, or the e2e suite directly (§7).

## 5. Data & persistence

`config/scenarios/*.yaml` is the **only** persisted application state
(`docs/SOLUTION_ARCHITECTURE.md` §2/§7) — one YAML file per named
scenario, containing real personal financial data, which is why the
directory's contents are gitignored (`.gitignore`'s own comment) while
the directory itself is tracked via `config/scenarios/.gitkeep`.

- **Backup**: copy `config/scenarios/` elsewhere. There is no database,
  no migration, and no schema version to worry about — it's plain YAML,
  readable and editable by hand if needed (`scenario/models.py` /
  `parse_scenario()` is the authoritative shape).
- **Restore**: copy the backed-up files back into `config/scenarios/`.
  No process restart is required — both `GET /scenarios` and the
  Streamlit Scenarios page read the directory fresh on each request.
- **Never** point `RP_BFF_BASE_URL`/a scratch BFF instance at your real
  `config/scenarios/` when testing, scripting, or running the e2e/smoke
  paths above — both already default to an isolated temp directory for
  exactly this reason; don't override that default against real data.
- **Validating a scenario file** without running a full simulation:
  `POST /scenarios/{name}/validate` (BFF), or the "Validate" action on
  the Streamlit Scenarios page.

## 6. Troubleshooting

**`ModuleNotFoundError: No module named 'retirement_planner'` (or
`rp_bff`/`rp_ui`) when starting `uvicorn`/`streamlit` directly.**
Some dev environments have the `uvicorn`/`streamlit` console-script
entry points hardcoded to a different Python interpreter than the one
the three project packages were installed into (this repo's own sandbox
has exactly this split — `.venv/bin/python` has the packages,
`.venv/bin/python3.12` doesn't). Fix: run `python -m uvicorn ...` /
`python -m streamlit run ...` with the interpreter you actually
`pip install -e`'d into, or use the `run-retirement-planner` skill (§3),
whose driver already encodes the correct interpreter for this repo.

**`driver.py smoke` fails with `ModuleNotFoundError: No module named
'playwright'`.** You ran it under the wrong interpreter — `smoke` needs
`.venv/bin/python3.12` (Playwright + Chromium live there), not the
interpreter the app packages are installed into. See §2's optional e2e
install step.

**UI loads but every action errors, or the fan chart/compare page never
returns data.** Almost always the BFF isn't reachable at the URL the UI
was started with. Confirm `RP_BFF_BASE_URL` was set in the same terminal
`streamlit run` was launched from, matches the BFF's actual host/port,
and includes the `/api/v1` suffix; then re-run the health check in §4
against that same URL.

**`Address already in use` on port 8000 or 8501.** A previous run's
process is still holding the port.
`ps aux | grep -E "uvicorn|streamlit"`, then `kill` the PID(s). A
`driver.py start` (§3) stopped with SIGINT or SIGTERM cleans up after
itself (both are handled to run the same teardown path); a process
started by hand and killed with `SIGKILL`, or one that outlived a crashed
terminal, won't self-clean and needs a manual `kill`.

**A `pip install -e` step fails, or a stale editable install shadows your
current checkout.** Reinstall in dependency order (§2) — core library
first, then `services/bff`, then `apps/streamlit_ui`. `rp-xwm` fixed a
real setuptools flat-layout package-discovery failure in the e2e
package's own editable install; if you hit an analogous error in one of
the three main packages, compare against that package's `pyproject.toml`
`[tool.setuptools.packages.find]` section before assuming it's
environment-specific.

**A scenario file fails to load with a validation error.** Expected,
not a bug: `POST /scenarios/{name}/validate` (or the UI's own Validate
action) reports exactly what's wrong against `scenario/validate()`'s
rules. Compare the offending YAML against a known-good example
(`examples/reference_scenario.py` builds one programmatically; any file
already round-tripped through the Scenarios page is another).

**A number in a report looks wrong, or a state/feature you expected
isn't modeled.** Check `docs/BRD.md` §5 (regulatory coverage table) and
§7 (known limitations) before assuming it's a bug — several gaps
(SC/DE's unverified placeholder brackets, no baseline Medicare/ACA
premiums, no self-employment tax, several Social Security provisions) are
documented, known, and surfaced via the `verified`/`figures_used`
mechanism (§7 of the architecture doc) rather than silently absorbed.

## 7. Testing & quality gates

Run before considering any change done — see `README.md`'s own Testing
section for exact current counts:

```bash
pytest tests/                                   # core library
pytest services/bff/tests/                      # BFF API service
pytest apps/streamlit_ui/tests/                  # Streamlit UI
cd e2e && ../.venv/bin/python3.12 -m pytest -q   # browser-driven e2e
```

```bash
ruff check src/ tests/ && ruff check services/bff/ && ruff check apps/streamlit_ui/
mypy --config-file pyproject.toml src/retirement_planner
mypy --config-file services/bff/pyproject.toml services/bff/src/rp_bff
mypy --config-file apps/streamlit_ui/pyproject.toml apps/streamlit_ui/src/rp_ui
bandit -r src/retirement_planner -ll && bandit -r services/bff/src/rp_bff -ll && bandit -r apps/streamlit_ui/src/rp_ui -ll
pip-audit --skip-editable
```

A change to `src/retirement_planner` should at minimum pass `pytest
tests/`; a change touching an HTTP contract or UI page should also pass
that layer's own suite plus e2e.

## 8. CI pipeline

`.github/workflows/ci.yml` runs on every push and every PR to `main`:

| Job | Runs | Gates the build? |
|---|---|---|
| `quality-gates` | ruff, mypy, bandit, pip-audit, then all three unit/integration suites, across all three packages | Yes — every check here is blocking |
| `e2e-tests` | Playwright browser suite, after `quality-gates` passes | Yes |
| `zap-api-scan` | OWASP ZAP DAST scan against a live BFF instance's OpenAPI spec, thresholded by `.zap/rules.tsv` | **No** — `continue-on-error: true`, pending its first few real-runner calibration passes (see the job's own comment in `ci.yml` for why); its HTML/JSON report is still uploaded as a build artifact every run, pass or fail |

**Interpreting a red build**: a failure in `quality-gates` or
`e2e-tests` blocks merge and must be fixed — reproduce locally with the
matching command in §7. A failed `zap-api-scan` does not block merge
today but its uploaded report (`zap-report.html`/`.json`, 30-day
retention) should still be read — a real finding there is real, even
though the job is report-only for now.

## 9. Annual figure refresh

`docs/SOLUTION_ARCHITECTURE.md` §8's "Architecture review: adaptability
to tax-law change (rp-sq9)" explains *why* this is normally a data
change, not a code change: every tax/mechanics figure is a
`SourcedFigure` whose `schedule: dict[year, value]` already repeats
today's pinned real-dollar value across every documented year
(`_DOCUMENTED_YEARS`, currently 2020-2074) — so a new year's IRS Rev.
Proc. / CMS IRMAA table / SSA COLA fact sheet does **not** by itself
break anything or require an urgent fix. This section is the checklist
for the maintenance decision "a new year's figures just published — do
we re-pin, and if so, how" (014-figure-verification's own methodology,
generalized past that feature's original one-time cleanup).

### 9.1 Which figures this applies to

| Figure(s) | Module | Primary source | Refresh cadence |
|---|---|---|---|
| Federal bracket thresholds (MFJ/single) | `tax/federal.py` | IRS Revenue Procedure (annual) | Inflation-indexed — re-pin is optional (§9.2) |
| IRMAA tiers (MFJ/single) | `tax/irmaa.py` | CMS.gov Medicare Parts B & D tables (annual) | Inflation-indexed — re-pin is optional |
| HSA contribution limits (self-only/family) | `mechanics/hsa.py` | IRS Revenue Procedure (annual) | Inflation-indexed — re-pin is optional; the $1,000 catch-up is fixed by statute (IRC §223(b)(3)) and never changes |
| SC/DE bracket tables | `tax/state/sc.py`, `tax/state/de.py` | SC Code Ann. §12-6-510, Del. Code Ann. tit. 30 §1102 | Still unverified placeholders (`verified=False`, `docs/BRD.md` §5.4) — a genuine first verification, not a re-pin, is the open task here; same procedure below once done |
| NIIT rate/thresholds | `tax/niit.py` | 26 U.S.C. §1411 | Fixed by statute since 2013 — touch only if Congress amends this section |
| SS provisional-income thresholds | `tax/social_security.py` | 26 U.S.C. §86(c) | Fixed by statute since 1984 — same |
| OASDI/Medicare FICA rates | `tax/fica.py` | 26 U.S.C. §3101 et seq. | Rates are fixed by statute; `OASDI_WAGE_BASE` genuinely grows yearly via national average wage indexing (a different, faster series than CPI) but this project holds it flat at its pinned year by the same real-dollar convention (module's own docstring) — `ADDITIONAL_MEDICARE_TAX_THRESHOLDS` is fixed by statute since 2013, not merely held flat |
| Early-withdrawal penalty rate | `tax/early_withdrawal_penalty.py` | 26 U.S.C. §72(t) | Fixed by statute |
| Roth conversion 5-year seasoning | `mechanics/roth_conversion_ladder.py` | 26 U.S.C. §408A | Fixed by statute |
| RMD start age | `mechanics/rmd.py` (`RMD_START_AGE`) | SECURE 2.0 Act §107 | Already encodes its one known future step (73→75 in 2033) as a two-part schedule — nothing to do unless Congress legislates *another* step |
| Uniform Lifetime / Joint Life / Single Life Expectancy tables | `mechanics/rmd.py`, `mechanics/inherited_rmd.py` | IRS Pub. 590-B, Appendix B | Revised by IRS only occasionally (not annually) when its underlying mortality assumptions change — watch for a new Pub. 590-B edition, not a yearly check |
| SS claiming-age/spousal/survivor adjustment formulas | `mechanics/social_security_benefit.py` | 42 U.S.C. §402 et seq. | Fixed statutory formulas |

If a new year's publication reveals a **structural** change (a bracket
added/removed, a new tier, a formula change) rather than a plain
inflation bump, that is not a data-only refresh — treat it like
`RMD_START_AGE`'s 2033 step: encode it as an additional keyed sub-range
in the schedule dict, and budget real design/review time, not just a
literal swap.

### 9.2 Procedure: re-pinning an inflation-indexed figure to a newer year

1. **Identify the module(s)** from the table above.
2. **Decide whether to re-pin at all.** The existing pinned year already
   satisfies every documented year through `_DOCUMENTED_YEARS`'s end
   (the whole point of the real-dollar convention,
   `docs/SOLUTION_ARCHITECTURE.md` §8) — re-pinning to a newer year is a
   deliberate "keep the citation current" maintenance choice, not a bug
   fix. Skip the rest of this procedure if the answer is no.
3. **Look up the new figure against its actual primary source** (the PDF
   Revenue Procedure, the CMS.gov table, the SSA fact sheet) — never
   from memory or a secondary summary, mirroring
   `specs/014-figure-verification/research.md` §1's own discipline. Note
   the specific section/page and the date checked.
4. **Update the schedule dict's literal values** — the whole
   `_DOCUMENTED_YEARS` range still repeats one flat value (or, for
   `federal.py`'s two-part brackets, one flat table); replace the old
   literal(s), don't add a second real per-year table.
5. **Update the `citation=` string** on that `SourcedFigure` to name the
   new source document and tax year, and set `last_verified` to today's
   date. Leave `verified=True` only if you actually did step 3 — an
   unconfirmed guess must ship as `verified=False` (Constitution
   Principle III; `docs/BRD.md` §7 is where an honestly-unverified figure
   gets disclosed, not silently marked verified to make a warning go
   away).
6. **Update the module's own docstring** if it names a specific tax
   year/citation inline (`tax/federal.py`'s docstring is the pattern to
   match).
7. **Update `docs/BRD.md` §5**'s verification table row for this figure
   (source, tax year, verified status) if any of those changed.
8. **Run that package's test suite** (`pytest tests/` at minimum;
   `services/bff/tests/`/`apps/streamlit_ui/tests/` too if a hardcoded
   expected figure appears in a fixture there) — a re-pin usually breaks
   at least one test asserting the old literal, which is expected and
   should be updated to the new one, not skipped.

### 9.3 A known future action: extending `_DOCUMENTED_YEARS` itself

Every schedule currently documents 2020-2074. A plan horizon that
reaches 2075 (a `plan_to_age` far enough out from a young household's
`current_age`) will raise `UnsupportedTaxYearError` — not urgent today,
but worth another pass once real usage approaches that edge. Extending
it is the same one-line `range(...)` change repeated across every
module in the table above, not a per-figure redesign.

## 10. Rollback

There is no deployed environment to roll back (§0) — "rollback" here
means the local checkout. Since every process is stateless outside
`config/scenarios/*.yaml` (§5):

```bash
git log --oneline -10          # find the commit to return to
git checkout <sha> -- .        # or: git revert <sha> for a shared branch
pip install -e ".[dev]" -e "services/bff[dev]" -e "apps/streamlit_ui[dev]"  # reinstall, in case dependencies changed
```

Restart the stack (§3). Scenario data in `config/scenarios/` is
untouched by any of the above — it's gitignored and lives independently
of the code checkout.

## 11. Related documents

- [`README.md`](../README.md) — install/run quick reference, project
  layout, development process.
- [`docs/SOLUTION_ARCHITECTURE.md`](SOLUTION_ARCHITECTURE.md) — what's
  actually deployed and how the pieces talk to each other.
- [`docs/BRD.md`](BRD.md) — what the system models, what it doesn't yet,
  and what's still unverified — the first place to check when a number
  looks wrong.
- [`.claude/skills/run-retirement-planner/SKILL.md`](../.claude/skills/run-retirement-planner/SKILL.md) —
  the automated launch/smoke-test path this runbook's §3/§6 summarize.
