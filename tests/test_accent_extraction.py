"""Tests for dynamic accent extraction (Milestone 5.10.23)."""

from gui.design.accent_extraction import extract_accent_from_pixels


def test_accent_prefers_vivid_color_over_grayscale():
    # Construct pixels: many gray tones + some vivid blue/green/red clusters
    gray = [(i, i, i) for i in range(40, 200, 20) for _ in range(30)]
    vivid = []
    vivid += [(20, 120, 240)] * 60  # strong blue
    vivid += [(10, 200, 80)] * 40  # green
    vivid += [
        (220, 40, 50)
    ] * 20  # red accent (fewer, likely lower score than blue due to value mix)
    result = extract_accent_from_pixels(gray + vivid, palette_size=4)
    assert result.source_count > 0
    # Accent should not be a gray (#RRGGBB where R=G=B) and should be in palette
    assert result.accent in result.palette
    r = int(result.accent[1:3], 16)
    g = int(result.accent[3:5], 16)
    b = int(result.accent[5:7], 16)
    assert not (r == g == b), f"Accent unexpectedly grayscale: {result.accent}"


def test_accent_fallback_when_only_grayscale():
    gray = [(i, i, i) for i in range(20, 220, 10)]
    result = extract_accent_from_pixels(gray, palette_size=3)
    # When only grayscale, accept first bucket average but must produce a valid hex
    assert result.accent.startswith("#") and len(result.accent) == 7
    assert result.source_count > 0


def test_palette_size_limit():
    pixels = [(255, 0, 0)] * 50 + [(0, 255, 0)] * 50 + [(0, 0, 255)] * 50
    result = extract_accent_from_pixels(pixels, palette_size=2)
    assert len(result.palette) == 2
    assert all(p.startswith("#") for p in result.palette)
