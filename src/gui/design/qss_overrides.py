"""User QSS override sandbox & validation.

Provides a constrained way for advanced users to inject additional QSS rules
without compromising security or visual consistency. Only a curated whitelist
of selectors and properties is allowed. Disallowed content is stripped; empty
rules are omitted.

Scope (Milestone 0.10 initial):
- Support simple selector types: QWidget, .class, #id
- Restrict properties to a safe token-aligned subset (colors, spacing-derived margins/padding, font sizes, border radius)
- For color values, encourage usage of existing tokens by allowing hex colors and rejecting functions (e.g., url(), rgba()) for now.

Future extensions:
- Allow rgba() with validation
- Provide token variable substitution (e.g., $accent)
- Add line/column error reporting for UI feedback
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, List, Sequence

__all__ = [
    "QSSValidationError",
    "sanitize_custom_qss",
    "VALID_PROPERTIES",
]


class QSSValidationError(ValueError):
    """Raised for critical structural QSS errors (currently unused; reserved)."""


# Whitelisted CSS-like properties users can override safely.
VALID_PROPERTIES = {
    "color",
    "background",
    "background-color",
    "padding",
    "padding-left",
    "padding-right",
    "padding-top",
    "padding-bottom",
    "margin",
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
    "font-size",
    "font-weight",
    "border-radius",
    "border",
    "border-color",
    "border-width",
    "border-style",
}

# Acceptable selector pattern: element | .class | #id (no combinators yet)
_SELECTOR_RE = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*|\.[A-Za-z_][A-Za-z0-9_]*|#[A-Za-z_][A-Za-z0-9_]*)$"
)

# Basic property line: key: value;  (value may have spaces until ;)
_DECL_RE = re.compile(r"^([a-zA-Z-]+)\s*:\s*([^;]+);?$")

# Allow hex colors (#rgb, #rgba, #rrggbb, #rrggbbaa) and simple numeric/px values
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,8})$")
_NUMERIC_RE = re.compile(r"^[0-9]{1,4}(?:px)?$")


def _split_rules(source: str) -> Iterable[str]:
    buf: List[str] = []
    brace = 0
    for ch in source:
        buf.append(ch)
        if ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1
            if brace == 0:
                rule = "".join(buf).strip()
                if rule:
                    yield rule
                buf = []
    # Ignore trailing partial rule (unbalanced)


def _valid_selector(sel: str) -> bool:
    return bool(_SELECTOR_RE.match(sel))


def _validate_value(prop: str, value: str) -> bool:
    v = value.strip()
    if prop in {"color", "background", "background-color", "border-color"}:
        return bool(_HEX_COLOR_RE.match(v))
    if (
        prop.startswith("padding")
        or prop.startswith("margin")
        or prop in {"border-width", "font-size", "border-radius"}
    ):
        # Accept up to 4 space-separated numeric tokens
        parts = v.split()
        if 1 <= len(parts) <= 4 and all(_NUMERIC_RE.match(p) for p in parts):
            return True
        return False
    if prop == "font-weight":
        return v in {"400", "500", "600", "700", "bold", "normal"}
    if prop == "border-style":
        return v in {"solid", "dashed", "none"}
    if prop == "border":
        # Very strict simple pattern: width style color
        segs = v.split()
        if len(segs) == 3:
            w, s, c = segs
            return (
                _NUMERIC_RE.match(w) and s in {"solid", "dashed", "none"} and _HEX_COLOR_RE.match(c)
            )
        return False
    return False


def sanitize_custom_qss(source: str) -> str:
    """Return a sanitized subset of user-provided QSS.

    Discards any rule with invalid selectors or zero valid declarations. Unknown
    properties or invalid values are skipped. Input outside balanced braces is ignored.
    Comments (/* ... */) are stripped early.
    """
    # Strip /* */ comments
    src = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    cleaned_rules: List[str] = []
    for raw_rule in _split_rules(src):
        if "{" not in raw_rule or "}" not in raw_rule:
            continue
        selector_part, body = raw_rule.split("{", 1)
        body = body.rsplit("}", 1)[0]
        selector = selector_part.strip()
        if not _valid_selector(selector):
            continue
        decls: List[str] = []
        for line in body.split(";"):
            line = line.strip()
            if not line:
                continue
            m = _DECL_RE.match(line if line.endswith(";") else line + ";")
            if not m:
                continue
            prop, value = m.group(1).lower(), m.group(2)
            if prop not in VALID_PROPERTIES:
                continue
            if not _validate_value(prop, value):
                continue
            decls.append(f"{prop}: {value.strip()};")
        if decls:
            cleaned_rules.append(f"{selector} {{\n  " + "\n  ".join(decls) + "\n}")
    return "\n\n".join(cleaned_rules) + ("\n" if cleaned_rules else "")
