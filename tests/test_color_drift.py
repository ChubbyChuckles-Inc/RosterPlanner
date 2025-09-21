"""Tests for color token drift detector (Milestone 0.23)."""

from gui.design.color_drift import scan_for_color_drift, normalize_hex


def test_normalize_hex_cases():
    assert normalize_hex("#abc") == "#AABBCC"
    assert normalize_hex("#AbC") == "#AABBCC"
    assert normalize_hex("#a1b2c3") == "#A1B2C3"
    assert normalize_hex("#abcd") == "#AABBCCDD"


def test_scan_for_drift(tmp_path):
    src = tmp_path / "sample.py"
    src.write_text(
        """
VALUE_ALLOWED = '#AABBCC'  # token color
VALUE_DISALLOWED = '#123456'
# comment with #FFFFFF not allowed
another = "#fff"  # short form not allowed
shade = '#abcd'  # 4-digit with alpha not allowed
""",
        encoding="utf-8",
    )

    allowed = {"#AABBCC"}
    issues = scan_for_color_drift([str(src)], allowed_hex_values=allowed)
    literals = sorted({i.normalized for i in issues})
    assert "#123456" in literals
    assert "#FFFFFF" in literals
    assert "#AABBCCDD" in literals
    assert "#FFFFFF" in literals
    # Ensure allowed one absent
    assert not any(i.normalized == "#AABBCC" for i in issues)
    # Count should match the distinct disallowed codes * occurrences (at least >=3)
    assert len(issues) >= 3
