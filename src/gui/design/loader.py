"""Design token loading and QSS generation utilities.

Responsibilities:
- Load tokens from JSON file into a typed structure.
- Provide validation & fallback defaults.
- Generate derived QSS variables for application-wide theming.

Usage:
    from gui.design import load_tokens
    tokens = load_tokens()
    qss = tokens.generate_qss()
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Dict, Mapping

_TOKEN_FILE = Path(__file__).parent / "tokens.json"


class TokenValidationError(RuntimeError):
    """Raised when required token fields are missing or malformed."""


@dataclass(slots=True)
class DesignTokens:
    raw: Mapping[str, Any]

    def color(self, *path: str, default: str | None = None) -> str:
        node: Any = self.raw.get("color", {})
        for p in path:
            if not isinstance(node, Mapping) or p not in node:
                if default is not None:
                    return default
                raise KeyError(f"Missing color token path: {'/'.join(path)}")
            node = node[p]
        if not isinstance(node, str):
            raise TypeError(f"Color token at {'/'.join(path)} must be a string")
        return node

    def spacing(self, key: str) -> int:
        value = self.raw.get("spacing", {}).get(key)
        if value is None:
            raise KeyError(f"Missing spacing token: {key}")
        if not isinstance(value, int):
            raise TypeError(f"Spacing token {key} must be int, got {type(value)}")
        return value

    def font_size(self, key: str) -> int:
        value = self.raw.get("typography", {}).get("scale", {}).get(key)
        if value is None:
            raise KeyError(f"Missing font size token: {key}")
        if not isinstance(value, int):
            raise TypeError(f"Font size token {key} must be int, got {type(value)}")
        return value

    def generate_qss(self) -> str:
        """Generate a QSS variable block mapping tokens to --rp-* custom props.

        While Qt's native style system doesn't support CSS custom properties,
        we still centralize a single QSS prelude for consistency & easier global replace.
        """
        lines: list[str] = ["/* AUTO-GENERATED FROM design tokens. Do not edit manually. */"]
        # Colors (flatten up to 3 levels deep)
        color_section = self.raw.get("color", {})
        for group_name, group_val in color_section.items():
            if isinstance(group_val, Mapping):
                for key, val in group_val.items():
                    if isinstance(val, str):
                        lines.append(f"/* color.{group_name}.{key} */")
                        lines.append(f"/* rp-{group_name}-{key}: {val}; */")
        # Typography (basic font sizes)
        scale = self.raw.get("typography", {}).get("scale", {})
        for key, val in scale.items():
            lines.append(f"/* font-size-{key}: {val}px; */")
        return "\n".join(lines) + "\n"


def load_tokens(path: str | Path | None = None) -> DesignTokens:
    """Load design tokens from JSON.

    Parameters
    ----------
    path: optional explicit path override.
    """
    token_path = Path(path) if path else _TOKEN_FILE
    if not token_path.exists():
        raise FileNotFoundError(f"Design token file not found: {token_path}")
    with token_path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    _validate_tokens(data)
    return DesignTokens(raw=data)


def _validate_tokens(data: Mapping[str, Any]) -> None:
    required_top = ["color", "spacing", "typography"]
    for key in required_top:
        if key not in data:
            raise TokenValidationError(f"Missing top-level token group: {key}")
    # Spot-check some mandatory nested keys
    if "background" not in data["color"]:
        raise TokenValidationError("color.background group required")
    if "scale" not in data["typography"]:
        raise TokenValidationError("typography.scale group required")


__all__ = ["DesignTokens", "load_tokens", "TokenValidationError"]
