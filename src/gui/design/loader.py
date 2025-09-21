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
from typing import Any, Dict, Mapping, Iterable, Literal

_TOKEN_FILE = Path(__file__).parent / "tokens.json"


class TokenValidationError(RuntimeError):
    """Raised when required token fields are missing or malformed."""


@dataclass
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

    # --- Typography Helpers -------------------------------------------------
    def heading_levels(self) -> Iterable[str]:
        headings = self.raw.get("typography", {}).get("headings", {})
        return headings.keys()

    def heading_font_size(self, heading: str, scale_factor: float = 1.0) -> int:
        """Return pixel font size for a heading key (e.g., 'h1').

        Applies an optional scale_factor (user preference / accessibility). Result
        is rounded to nearest integer to keep pixel alignment predictable.
        """
        typography = self.raw.get("typography", {})
        headings = typography.get("headings", {})
        token_key = headings.get(heading)
        if token_key is None:
            raise KeyError(f"Unknown heading level: {heading}")
        base_px = self.font_size(token_key)
        scaled = int(round(base_px * scale_factor))
        return max(1, scaled)

    def font_family(self) -> str:
        fam = self.raw.get("typography", {}).get("fontFamily")
        if not isinstance(fam, str):
            raise TokenValidationError("typography.fontFamily must be a string")
        return fam

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

    # --- Theme Variant Helpers --------------------------------------------
    def theme_variant(
        self, variant: Literal["default", "high-contrast"] = "default"
    ) -> Mapping[str, str]:
        """Return a flattened mapping of semantic colors for a theme variant.

        High contrast variant uses *HighContrast groups when present, otherwise
        falls back to base groups. This is a lightweight indirection layer;
        full theming system (runtime switching + QSS regen) will build atop this.
        """
        color = self.raw.get("color", {})
        result: Dict[str, str] = {}

        def _copy(prefix: str, group_name: str, alt_group: str | None = None):
            grp = color.get(group_name, {})
            if variant == "high-contrast" and alt_group:
                grp = color.get(alt_group, grp)
            if isinstance(grp, Mapping):
                for k, v in grp.items():
                    if isinstance(v, str):
                        result[f"{prefix}.{k}"] = v

        _copy("background", "background", "backgroundHighContrast")
        _copy("surface", "surface", "surfaceHighContrast")
        _copy("text", "text", "textHighContrast")
        _copy("accent", "accent", "accentHighContrast")
        _copy("border", "border", None)
        return result

    def is_high_contrast_supported(self) -> bool:
        col = self.raw.get("color", {})
        return any(k.endswith("HighContrast") for k in col.keys())


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
    typo = data["typography"]
    if "scale" not in typo:
        raise TokenValidationError("typography.scale group required")
    if "headings" not in typo:
        raise TokenValidationError("typography.headings group required")
    # Validate heading mapping references existing scale entries
    scale = typo.get("scale", {})
    headings = typo.get("headings", {})
    if not isinstance(headings, Mapping):
        raise TokenValidationError("typography.headings must be a mapping")
    for h, token_ref in headings.items():
        if token_ref not in scale:
            raise TokenValidationError(f"Heading {h} references unknown scale token '{token_ref}'")


__all__ = ["DesignTokens", "load_tokens", "TokenValidationError"]
