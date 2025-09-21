"""Simple linter for state diagram markdown files.

Checks that each targeted markdown file under docs/state_diagrams contains at
least one Mermaid fenced block. Returns exit code 0 on success, 1 on failure.

Usage (future CI integration):
    python scripts/validate_state_diagrams.py
"""

from __future__ import annotations

from pathlib import Path
import sys

TARGET_DIR = Path(__file__).parent.parent / "docs" / "state_diagrams"


def file_has_mermaid(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    fence = "```mermaid"
    return fence in text


def main() -> int:
    if not TARGET_DIR.exists():
        print("state_diagrams directory missing", file=sys.stderr)
        return 1
    md_files = list(TARGET_DIR.glob("*.md"))
    if not md_files:
        print("no markdown files found", file=sys.stderr)
        return 1
    missing = [p.name for p in md_files if not file_has_mermaid(p)]
    if missing:
        print("Files missing mermaid block: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(f"Validated {len(md_files)} state diagram file(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
