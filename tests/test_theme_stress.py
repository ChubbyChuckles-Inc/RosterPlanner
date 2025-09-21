from gui.design.theme_stress import run_theme_stress
from gui.design.loader import DesignTokens
import pytest


def _fake_tokens(high_contrast: bool = True) -> DesignTokens:
    color = {
        "background": {"base": "#FFFFFF"},
        "surface": {"base": "#F8F9FA"},
        "text": {"primary": "#222222"},
        "accent": {"primary": "#3366FF"},
        "border": {"subtle": "#E0E0E0"},
    }
    if high_contrast:
        color.update(
            {
                "backgroundHighContrast": {"base": "#000000"},
                "surfaceHighContrast": {"base": "#121212"},
                "textHighContrast": {"primary": "#FFFFFF"},
                "accentHighContrast": {"primary": "#99C2FF"},
            }
        )
    raw = {
        "color": color,
        "spacing": {"xs": 4},
        "typography": {"scale": {"base": 14}, "headings": {"h1": "base"}},
    }
    return DesignTokens(raw=raw)


def test_theme_stress_basic():
    tokens = _fake_tokens()
    report = run_theme_stress(tokens, iterations=10)
    assert report.iterations == 10
    assert report.total_errors() == 0
    assert report.accent_bases  # non-empty
    assert all(isinstance(c, int) and c >= 0 for c in report.diff_counts)


def test_theme_stress_invalid_iterations():
    with pytest.raises(ValueError):
        run_theme_stress(_fake_tokens(), iterations=0)


def test_theme_stress_no_high_contrast():
    tokens = _fake_tokens(high_contrast=False)
    report = run_theme_stress(tokens, iterations=5)
    assert report.meta["variant_cycle"] == ["default"]
    assert report.total_errors() == 0
