"""Custom theme import utilities (Milestone 1.6.2).

Allows users to supply a JSON file containing partial color overrides. Schema:

{
  "color": {
     "background": { "primary": "#FFFFFF" },
     "accent": { "base": "#FF5722" }
  }
}

Only recognized nested color groups are merged. Other top-level keys are ignored
for now (future: spacing, typography). Validation is intentionally lenient:
invalid structures raise `CustomThemeError`.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, Mapping

__all__ = ["load_custom_theme", "CustomThemeError"]


class CustomThemeError(RuntimeError):
    pass


def load_custom_theme(path: str | Path) -> Mapping[str, str]:
    p = Path(path)
    if not p.exists():  # pragma: no cover - defensive
        raise FileNotFoundError(p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:  # noqa: F841
        raise CustomThemeError(f"Invalid JSON: {e}") from e
    if not isinstance(data, Mapping):
        raise CustomThemeError("Root of custom theme must be an object")
    color = data.get("color", {})
    if not isinstance(color, Mapping):
        raise CustomThemeError("'color' key must map to an object")
    flat: Dict[str, str] = {}
    for group_name, group_val in color.items():
        if not isinstance(group_val, Mapping):
            continue  # skip invalid group
        for k, v in group_val.items():
            if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7):
                flat[f"{group_name}.{k}"] = v
    return flat
