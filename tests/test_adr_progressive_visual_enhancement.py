from pathlib import Path


def test_adr_0002_progressive_visual_enhancement_exists():
    p = Path("docs/adr/ADR-0002-progressive-visual-enhancement-strategy.md")
    assert p.exists(), "Expected ADR-0002 file to exist for progressive visual enhancement strategy"
    text = p.read_text(encoding="utf-8")
    assert "Progressive Visual Enhancement Strategy" in text
    assert "Decision" in text
    assert "Alternatives Considered" in text
