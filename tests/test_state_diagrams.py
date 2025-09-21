from pathlib import Path


def test_state_diagram_markdown_files_exist():
    base = Path(__file__).parent.parent / "docs" / "state_diagrams"
    assert (base / "command_palette_state.md").exists()
    assert (base / "planner_scenario_editor_state.md").exists()


def test_state_diagram_files_contain_mermaid_blocks():
    base = Path(__file__).parent.parent / "docs" / "state_diagrams"
    for md in base.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        assert "```mermaid" in text, f"Missing mermaid fence in {md.name}"
