"""JSON serialization for retirement_planner dataclasses (research.md §3):
a single recursive to_jsonable() function, not bare dataclasses.asdict(),
so date fields and PercentileBand's non-string-keyed percentiles dict get
JSON-legal, purpose-shaped renderings rather than crashing or losing data.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively converts obj into something json.dumps() can serialize
    directly:
      - datetime.date -> obj.isoformat() (ISO 8601 string)
      - dict -- if every key is a float, [{"percentile": k, "value": v}, ...]
        (lossless, and the shape a chart-drawing UI wants natively for
        PercentileBand.percentiles specifically); otherwise recurses into
        values, keeping string keys as-is
      - tuple -> list, recursively converted
      - dataclass instance -> dict, recursively converted field-by-field
      - list -> list, recursively converted
      - anything else (str, int, float, bool, None) -> returned unchanged
    """
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {field.name: to_jsonable(getattr(obj, field.name)) for field in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        if obj and all(isinstance(key, float) for key in obj):
            return [{"percentile": key, "value": to_jsonable(value)} for key, value in sorted(obj.items())]
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(item) for item in obj]
    return obj
