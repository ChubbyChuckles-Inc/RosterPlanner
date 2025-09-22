"""Sanity test ensuring required ADR documents exist (Milestone 5.9.23)."""

from __future__ import annotations

from pathlib import Path


def test_adr_0001_exists():
    p = Path("docs/adr/ADR-0001-ingestion-lifecycle-and-repository-abstraction.md")
    assert p.exists(), "Expected ADR-0001 markdown file to exist"
    content = p.read_text(encoding="utf-8")
    # Basic sanity anchors
    assert "Ingestion Lifecycle" in content
    assert "Repository Abstraction" in content
    assert "Decision" in content
