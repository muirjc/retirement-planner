# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## Build & Test

Four independent test suites — see [README.md#testing](README.md#testing) for exact commands and current counts:

```bash
pytest tests/                                   # core library
pytest services/bff/tests/                      # BFF API service
pytest apps/streamlit_ui/tests/                 # Streamlit UI
cd e2e && ../.venv/bin/python3.12 -m pytest -q  # browser-driven e2e (Playwright)
```

Run the layer(s) touched by your change, not necessarily all four — but a change to `src/retirement_planner` should at minimum pass `pytest tests/` before being considered done.

## Architecture Overview

Three deployable packages (core library → BFF → Streamlit UI) plus an e2e test harness — full detail, including C4 diagrams, in [docs/SOLUTION_ARCHITECTURE.md](docs/SOLUTION_ARCHITECTURE.md). What this tool models — regulations covered, math used, verification status of each figure — is in [docs/BRD.md](docs/BRD.md).

## Conventions & Patterns

This project is built with a spec-driven workflow (`specs/NNN-*/spec.md` → `plan.md` → `tasks.md`, checked against `.specify/memory/constitution.md`'s principles — accuracy over cleverness, reproducibility, auditability, extensibility, offline-first, performance budget). See `README.md`'s "Development process" section.

**Living documentation — update these in the same change, not a follow-up pass:**

- **`README.md`** — when a package, dependency, run command, or test count changes.
- **`docs/BRD.md`** — when a feature adds/changes a regulated figure (a new `SourcedFigure`), a tax rule, or a piece of financial math, or when a figure's `verified` status changes.
- **`docs/SOLUTION_ARCHITECTURE.md`** — when a package boundary, BFF route, UI page, or core subpackage's dependency chain changes.

Treat a stale diagram or stale figure-verification table the same as a stale `spec.md` — it's a defect to fix, not background noise to route around. If you're not sure whether a change is substantive enough to warrant an update, err toward updating.
