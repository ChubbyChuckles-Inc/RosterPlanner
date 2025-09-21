"""Tests for plugin style contract (Milestone 0.27)."""

from gui.design.plugin_style_contract import (
    validate_style_mapping,
    scan_plugin_style_files,
    PluginStyleIssue,
)


def test_validate_style_mapping_valid():
    mapping = {"button.bg": "token:color/surface", "button.fg": "token:color/text"}
    issues = validate_style_mapping(mapping)
    assert issues == []


def test_validate_style_mapping_invalid_hex():
    mapping = {"bg": "#AABBCC", "fg": "token:color/text"}
    issues = validate_style_mapping(mapping)
    kinds = {i.kind for i in issues}
    assert "raw-hex" in kinds


def test_scan_plugin_style_files(tmp_path):
    # create file with style mapping
    file = tmp_path / "plugin_styles.py"
    file.write_text(
        """STYLE_BUTTON = {\n    'bg': 'token:color/surface',\n    'fg': '#112233'\n}\n""",
        encoding="utf-8",
    )
    issues = scan_plugin_style_files([str(file)])
    assert any(i.kind == "raw-hex" for i in issues)
