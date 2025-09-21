"""Tests for inline style lint rule (Milestone 0.24)."""

from gui.design.inline_style_lint import scan_for_inline_styles, InlineStyleIssue


def test_detects_setStyleSheet(tmp_path):
    p = tmp_path / "sample.py"
    p.write_text(
        """
widget.setStyleSheet("background: red;")
# allowed usage example
another.setStyleSheet("color: blue;")  # inline-style-ok
""",
        encoding="utf-8",
    )
    issues = scan_for_inline_styles([str(p)])
    cats = [i.category for i in issues]
    assert "setStyleSheet" in cats
    # allowed line suppressed
    assert not any(i.snippet.endswith('blue;")') for i in issues)


def test_detects_style_attribute(tmp_path):
    p = tmp_path / "frag.html"
    p.write_text('<div style="color: #fff;">X</div>', encoding="utf-8")
    issues = scan_for_inline_styles([str(p)])
    assert any(i.category == "style-attr" for i in issues)


def test_detects_multiline_qss(tmp_path):
    p = tmp_path / "style_block.py"
    p.write_text('STYLESHEET = """QPushButton { color: red; }"""', encoding="utf-8")
    issues = scan_for_inline_styles([str(p)])
    assert any(i.category == "multiline-qss" for i in issues)
