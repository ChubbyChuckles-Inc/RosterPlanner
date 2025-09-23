from pathlib import Path


def test_motion_choreography_map_exists():
    p = Path("docs/motion_choreography_map.md")
    assert p.exists(), "Expected motion choreography map to exist (Milestone 5.10.26)"
    content = p.read_text(encoding="utf-8")
    # Basic sanity: ensure key headings are present
    for heading in [
        "Purpose",
        "Core Choreography Principles",
        "Sequencing Patterns",
        "Accessibility & Reduced Motion",
        "Performance Budget",
        "Testing Strategy",
    ]:
        assert heading in content, f"Heading '{heading}' missing from motion choreography map"
