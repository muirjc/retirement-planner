# Data Model: Instructions Page

Source: [spec.md](./spec.md) Functional Requirements, resolved against `apps/streamlit_ui/pages/1_Scenarios.py`'s actual fields (read during planning). Like `008`'s own reporting-adjacent pieces, this feature defines no domain entity in the `retirement_planner` sense — its one "entity" is the content itself.

## Section (`src/rp_ui/instructions_content.py`)

```python
@dataclass
class Section:
    title: str
    body: str  # Markdown -- rendered via st.markdown()
```

`SECTIONS: list[Section]` is the module's one export — an ordered list, rendered top to bottom by `pages/0_Instructions.py` with nothing more than a loop over `st.header(section.title)` / `st.markdown(section.body)`.

## The seven required sections (FR-002 through FR-007)

Each row is a content requirement, not literal copy — the actual prose is an implementation detail for `/speckit-tasks`/`/speckit-implement` to write, grounded in `docs/instructions_page_requirements.md` §5.

| Section | Must state (traced to FR) |
|---|---|
| Household / parties | Per party: name, current age, SS claiming age, SS benefit *at that claiming age* — not automatically the full-retirement-age figure (FR-004). |
| Accounts | Traditional/Roth/taxable balances are one **combined household total per type**, not per party (FR-003). |
| Spending | Annual figure is in **today's dollars**, before taxes (FR-005). |
| State | Points to the Scenarios page's own live state selector for the current supported list — never states specific codes here (FR-006). |
| Market assumptions | Any example allocation/return figure is framed as a starting point, never as *the* required or authoritative value (FR-007). |
| Simulation settings | Plain-language meaning of paths/seed/plan-to-age (spec.md §5, `docs/instructions_page_requirements.md` §5). |
| Roth conversion (optional) | When to leave it unchecked vs. fill it in; what "window" means (spec.md §5). |

## Relationships

- `pages/0_Instructions.py` imports `SECTIONS` and renders it — it holds no content of its own and makes no decision about ordering (the list's own order is the render order).
- No relationship to any `retirement_planner`/`rp_bff` type — this module imports nothing from either, the same containment `008` already enforces for the rest of `apps/streamlit_ui`, extended here to mean *no* import from `rp_ui.api_client` either (data-model.md's own novelty for this feature — every prior page imported it).

## State transitions

None. `SECTIONS` is a module-level constant, evaluated once at import time, identical on every render. No `st.session_state` entry belongs to this page.
