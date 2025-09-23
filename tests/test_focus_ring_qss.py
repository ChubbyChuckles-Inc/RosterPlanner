from gui.services.theme_service import ThemeService


def test_focus_ring_qss_contains_outline_rules():
    svc = ThemeService.create_default()
    qss = svc.generate_qss()
    # Expect focus selectors and outline
    assert "QPushButton:focus" in qss
    assert "outline: 2px solid" in qss


"""Test that the generated QSS contains unified focus ring styling.

Covers roadmap task 5.10.8 (Focus ring audit & unification).
"""

from gui.services.theme_service import ThemeService
from gui.design import ThemeManager, load_tokens


def test_focus_ring_rule_present():
    svc = ThemeService.create_default()
    qss = svc.generate_qss()
    # Ensure selector group and outline property appear
    assert "Focus Ring Unification" in qss
    assert "outline: 2px solid" in qss
    # Must reference border.focus or fallback accent
    assert "border.focus" not in qss  # value should already be resolved to hex
    # Basic sanity: a hex color after outline rule
    import re

    m = re.search(r"outline: 2px solid (#?[0-9a-fA-F]{3,6})", qss)
    assert m, qss
