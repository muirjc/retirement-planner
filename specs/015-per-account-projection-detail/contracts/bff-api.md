# Contract: `services/bff` HTTP API (addendum to `007`, `010`, `011`, `012`)

Extends `specs/007-bff-api-service/contracts/bff-api.md` with one
additive request field on both `SimulationRequest` and
`ComparisonRequest`, and one new `account_detail` response key on
`POST /simulations`, `POST /comparisons/deterministic`, and
`POST /comparisons/simulated`. No existing response key changes shape;
`account_detail` is purely additive JSON, same `to_jsonable()` convention
every other response field already uses.

## Modified request schemas (`schemas.py`)

```python
class SimulationRequest(BaseModel):
    # ...existing fields, unchanged...
    detail_path_index: int | None = None   # NEW -- which path's account_detail to compute; default 0


class ComparisonRequest(BaseModel):
    # ...existing fields, unchanged...
    detail_path_index: int | None = None   # NEW -- same meaning; ignored for the deterministic route
```

## `POST /simulations` — new response key

```text
POST /api/v1/simulations
  ...
  -> 200 {"run": ..., "summary": ..., "account_detail": [PlanYearAccountDetail, ...]}
     account_detail: reporting-api.md's PlanYearAccountDetail list, computed
     for run.path_results[detail_path_index or 0] (data-model.md).
  -> 422 {"error": "path_index_out_of_range", "requested": int, "path_count": int}
     when detail_path_index is given and out of [0, len(path_results)) --
     mirrors the existing unsupported_tax_year_error() shape (resolution.py).
```

## `POST /comparisons/deterministic` / `POST /comparisons/simulated` — new response key

```text
POST /api/v1/comparisons/deterministic
POST /api/v1/comparisons/simulated
  ...
  -> 200 {"axis": ..., "summaries": [...], "account_detail": [[PlanYearAccountDetail, ...], ...]}
     account_detail[i] corresponds to summaries[i] -- same candidate order
     result.projections / result.runs already iterate in. For the
     deterministic route, each candidate's own single PlanProjection *is*
     the "path" -- detail_path_index is accepted but ignored there.
  -> 422 {"error": "path_index_out_of_range", ...}   (simulated route only,
     same shape as the /simulations case, applied per-candidate -- the
     first out-of-range candidate found is reported)
```

## Modified internal resolution — not a wire-contract change, documented for downstream-feature awareness

Both comparison routes already compute the full `ComparisonResult`/
`SimulationComparisonResult` (`result`) before summarizing it, then
previously discarded `result` after building `summaries` — this feature
also passes `result` (and the resolved `Scenario.accounts`) to the new
`rp_bff.account_detail.build_account_detail_for_projection()`/
`build_account_detail_for_run()` before it goes out of scope.
`compute_account_shares()` (reporting-api.md) is called once per request
(shared across every candidate in a comparison), not once per candidate,
since it depends only on the shared `Scenario.accounts`, not on any
candidate's own result.

## Consumption expectations for downstream features

- A future second UI builds its per-account detail view against
  `account_detail` exactly as it already builds against every other
  response field — nothing about this shape is Streamlit-specific.
- A client that doesn't send `detail_path_index` gets path 0's detail by
  default — the same "always present, sensible default" convention this
  BFF already uses elsewhere (e.g. `plan_to_age`/`n_paths`/`seed`
  resolving from the scenario's own `SimulationSettings` when omitted,
  `011`'s `resolve_run_context()`).
