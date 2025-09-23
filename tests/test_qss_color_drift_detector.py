"""Test (Milestone 5.10.41): QSS inline color drift detector.

Scans project source for disallowed hardcoded hex color literals that could
indicate drift away from central design tokens. This protects against
"magic" colors sneaking into code rather than being declared in tokens.

Allowed Patterns / Whitelist:
 - Token definition modules under gui/design (they are the source of truth)
 - Test files may include sample colors if they are part of semantic tests;
   a small explicit whitelist of literal values is permitted.
 - Common placeholders (#000, #fff, #FFFFFF, #000000) are allowed in a limited
   set of contexts (e.g., fallbacks, contrast tests) but we still encourage
   tokens; thus they remain allowed to reduce noise for now.

Fail Criteria:
 - Any other #RRGGBB or #RGB hex literal in non-design, non-test utility code.

Rationale:
 - Keeps design surface cohesive.
 - Encourages adding new palette entries via the token system with metadata.
"""

from __future__ import annotations
import re
from pathlib import Path

HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})\b")

ALLOWED_SIMPLE = {"#000", "#fff", "#FFF", "#FFFFFF", "#000000"}

# Transitional explicit whitelist: existing hardcoded values scheduled for tokenization.
# Each entry should gain a design token or be removed; tracked under a future
# polish milestone. Adding new literals should NOT extend this list without
# architectural review.
TRANSITIONAL_WHITELIST = {
    "#FF5722",  # custom_theme accent placeholder
    "#FF8800",  # tab metadata highlight (legacy)
    "#202020",  # fallback bg in theme_service.generate_qss
    "#3D8BFD",  # fallback accent/link color
    "#ffffff",  # doc area bg fallback (lowercase variant)
    "#202830",  # main_window custom frame color placeholder
    "#FF00AA",  # plugin style contract demo accent
}

ROOT = Path(__file__).resolve().parents[1]


def is_design_token_path(p: Path) -> bool:
    # Permit any file under gui/design as source of colors
    parts = p.parts
    try:
        gi = parts.index("gui")
        if len(parts) > gi + 1 and parts[gi + 1] == "design":
            return True
    except ValueError:
        return False
    return False


def test_no_inline_hex_color_drift():
    offenders = []
    for py_file in ROOT.rglob("*.py"):
        if ".venv" in py_file.parts:
            continue
        rel = py_file.relative_to(ROOT)
        # Skip tests themselves (except this detector) to reduce false positives
        if rel.parts[0] == "tests" and py_file.name != Path(__file__).name:
            continue
        if is_design_token_path(py_file):
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for m in HEX_RE.finditer(text):
            literal = m.group(0)
            if literal in ALLOWED_SIMPLE or literal in TRANSITIONAL_WHITELIST:
                continue
            offenders.append((str(rel), literal))
    assert not offenders, (
        "Found disallowed hardcoded color literals (add tokens or whitelist carefully):\n"
        + "\n".join(f"{path}: {color}" for path, color in offenders[:50])
    )
