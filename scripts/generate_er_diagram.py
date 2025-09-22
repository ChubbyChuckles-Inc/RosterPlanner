"""Generate ER Diagram Markdown (Milestone 3.1.1)

Usage:
    python -m scripts.generate_er_diagram

This script creates or updates `docs/source/schema_er_diagram.md` by
embedding a Mermaid ER diagram generated from the live schema.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from db import apply_schema, generate_er_mermaid

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "source" / "schema_er_diagram.md"

HEADER_PREFIX = "# SQLite Schema ER Diagram"


def update_doc(diagram: str) -> None:
    if DOC_PATH.exists():
        original = DOC_PATH.read_text(encoding="utf-8").splitlines()
    else:
        original = [HEADER_PREFIX, ""]

    # Rebuild content preserving only the header lines until a code fence start
    new_lines = []
    header_done = False
    for line in original:
        if line.strip().startswith("```mermaid"):
            header_done = True
            break
        new_lines.append(line)
    if not header_done:
        new_lines.append("")
    new_lines.append("```mermaid")
    new_lines.extend(diagram.rstrip().splitlines())
    new_lines.append("```")
    DOC_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> None:
    # Use in-memory DB
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    diagram = generate_er_mermaid(conn)
    update_doc(diagram)
    print("Updated ER diagram at", DOC_PATH)


if __name__ == "__main__":  # pragma: no cover
    main()
