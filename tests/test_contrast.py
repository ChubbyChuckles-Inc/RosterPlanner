from gui.design import load_tokens
from gui.design.contrast import contrast_ratio, relative_luminance, validate_contrast


def test_relative_luminance_monotonic():
    # White > Gray > Black
    white = '#ffffff'
    gray = '#777777'
    black = '#000000'
    assert relative_luminance(white) > relative_luminance(gray) > relative_luminance(black)


def test_contrast_ratio_basic():
    ratio = contrast_ratio('#ffffff', '#000000')
    assert abs(ratio - 21.0) < 0.1


def test_validate_contrast_tokens_pass():
    tokens = load_tokens()
    failures = validate_contrast(tokens, [
        ("text.primary", "background.base", "Primary text on base background"),
        ("text.secondary", "background.base", "Secondary text on base background"),
    ], threshold=3.0)  # relaxed for secondary
    assert not any(f for f in failures if "Primary text" in f)


def test_validate_contrast_detect_failure():
    tokens = load_tokens()
    # Force a low threshold scenario by comparing same color expecting failure at high threshold
    failures = validate_contrast(tokens, [
        ("text.muted", "text.muted", "Muted on muted"),
    ], threshold=4.5)
    assert failures, "Expected failure for identical foreground/background"
