from gui.design.qss_overrides import sanitize_custom_qss_detailed, apply_user_overrides


def test_detailed_result_counts():
    src = """
    QWidget { color: #fff; bad-prop: 1; padding: 4px; }
    QPushButton QPushButton { color: #000; }
    #box { border: 2px solid #123456; font-weight: ultra; }
    """
    res = sanitize_custom_qss_detailed(src)
    # QWidget rule accepted with 2 valid declarations
    assert res.accepted_rules == 2  # QWidget + #box
    assert res.dropped_rules >= 1  # invalid selector combinator
    assert res.accepted_declarations >= 3  # color, padding, border
    assert any(sel.strip() == "QPushButton QPushButton" for sel in res.selector_warnings)
    assert any(p[1] == "bad-prop" for p in res.property_warnings)
    assert any(p[1] == "font-weight" for p in res.property_warnings)  # invalid value


def test_apply_user_overrides_combines():
    base = "/* base */\nQWidget { color: #000; }\n"
    user = "QWidget { color: #111; }"
    combined, res = apply_user_overrides(base, user)
    assert "/* User Overrides */" in combined
    assert res.accepted_rules == 1
    assert combined.count("QWidget") >= 2


def test_apply_user_overrides_empty_no_dup_newline():
    base = "/* base */\n"
    user = "Invalid Selector { color: #fff; }"
    combined, res = apply_user_overrides(base, user)
    assert combined == base  # unchanged
    assert res.accepted_rules == 0
