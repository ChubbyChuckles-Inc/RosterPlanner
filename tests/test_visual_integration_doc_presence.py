from pathlib import Path


def test_visual_integration_guide_exists():
    p = Path("docs/visual_integration_guide.md")
    assert p.exists(), "Expected visual integration guide to exist (Milestone 5.10.19)"
