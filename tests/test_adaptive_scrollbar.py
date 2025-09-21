from gui.design.adaptive_scrollbar import build_scrollbar_styles


def test_basic_qss_generation():
    theme_map = {
        "surface.scroll.track": "#111111",
        "surface.scroll.trackHover": "#121212",
        "surface.scroll.handle": "#222222",
        "surface.scroll.handleHover": "#232323",
        "surface.scroll.handleActive": "#242424",
        "border.focus": "#00aaff",
        "surface.primary": "#101010",
        "background.base": "#000000",
        "accent.primary": "#ff0080",
    }
    qss = build_scrollbar_styles(theme_map, width=12, radius=6)
    assert "QScrollBar:vertical" in qss
    assert "width: 12px" in qss
    assert "border-radius: 6px" in qss
    assert "#111111" in qss  # track
    assert "#242424" in qss  # active handle
    # We expect base, hover, and pressed selectors for each orientation.
    assert "QScrollBar::handle:vertical" in qss
    assert "QScrollBar::handle:vertical:hover" in qss
    assert "QScrollBar::handle:vertical:pressed" in qss
    assert "QScrollBar::handle:horizontal" in qss
    assert "QScrollBar::handle:horizontal:hover" in qss
    assert "QScrollBar::handle:horizontal:pressed" in qss


def test_fallbacks_when_keys_missing():
    # Only provide minimal keys; others should fallback to surface.primary or background.base or placeholder.
    theme_map = {
        "surface.primary": "#333333",
        "background.base": "#202020",
        "accent.primary": "#ff00ff",
    }
    qss = build_scrollbar_styles(theme_map, width=8, radius=3)
    # Should still include selectors
    assert "QScrollBar:horizontal" in qss
    # Fallback colors should appear (surface.primary)
    assert "#333333" in qss
    # Width clamp respected and applied
    assert "width: 8px" in qss or "height: 8px" in qss


def test_parameter_clamping():
    theme_map = {"surface.primary": "#050505", "background.base": "#000000"}
    qss_small = build_scrollbar_styles(theme_map, width=1, radius=-5)  # clamps to width 4, radius 0
    assert "width: 4px" in qss_small or "height: 4px" in qss_small
    assert "border-radius: 0px" in qss_small
    qss_large = build_scrollbar_styles(
        theme_map, width=100, radius=99
    )  # clamps to width 30, radius 16
    assert "width: 30px" in qss_large or "height: 30px" in qss_large
    assert "border-radius: 16px" in qss_large
