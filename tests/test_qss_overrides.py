from gui.design.qss_overrides import sanitize_custom_qss


def test_allow_basic_rule():
    src = "QWidget { color: #fff; padding: 8; }"
    out = sanitize_custom_qss(src)
    assert "color: #fff;" in out
    assert "padding: 8;" in out
    assert out.strip().startswith("QWidget")


def test_reject_disallowed_property():
    src = ".Panel { position: absolute; color: #ffffff; }"
    out = sanitize_custom_qss(src)
    # position should be stripped, color retained
    assert "color: #ffffff;" in out
    assert "position" not in out


def test_reject_invalid_selector():
    src = "QWidget QPushButton { color: #fff; }"  # combinator not allowed
    out = sanitize_custom_qss(src)
    assert out.strip() == ""


def test_invalid_value_border():
    src = "#box { border: 1 solid red; }"  # color not hex
    out = sanitize_custom_qss(src)
    assert out.strip() == ""


def test_border_compound_valid():
    src = "#box { border: 2px solid #abcdef; }"
    out = sanitize_custom_qss(src)
    assert "border: 2px solid #abcdef;" in out


def test_comment_stripping_and_partial_rule():
    src = "/* comment */ QWidget { color: #123; /* inner */ margin: 4px; } .Bad { bad: 1; }"
    out = sanitize_custom_qss(src)
    assert "color: #123;" in out
    assert "margin: 4px;" in out
    assert "bad:" not in out


def test_multiple_spacing_values():
    src = "QWidget { padding: 4px 8px 4px 8px; }"
    out = sanitize_custom_qss(src)
    assert "padding: 4px 8px 4px 8px;" in out


def test_font_weight_and_style_limits():
    src = "#id { font-weight: 700; } #id2 { font-weight: ultra; }"
    out = sanitize_custom_qss(src)
    assert "#id" in out
    assert "font-weight: 700;" in out
    assert "ultra" not in out
