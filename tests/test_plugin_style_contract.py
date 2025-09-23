from __future__ import annotations

from gui.services.plugin_style_contract import StyleContractValidator


def test_validator_flags_disallowed_and_allows_whitelist():
    mapping = {"text.primary": "#FFFFFF", "background.primary": "#101010", "accent.base": "#3D8BFD"}
    validator = StyleContractValidator.from_theme_mapping(mapping, whitelist=["#000000"])
    qss = "QLabel { color:#FFFFFF; background:#FF00AA; border:1px solid #000000; }"
    report = validator.scan_stylesheet(qss)
    assert report.disallowed == 1
    assert any(i.normalized == "#FF00AA" for i in report.issues)
    assert report.allowed >= 2
