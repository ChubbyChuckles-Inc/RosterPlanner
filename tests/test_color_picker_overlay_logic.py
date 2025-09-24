"""Logic-level tests for ColorPickerOverlay support helpers.

These tests avoid full GUI interaction (which would require a running
QApplication and real screen sampling) and instead validate that the
nearest token suggestion logic and dismissal behavior wiring are
accessible. We mock a minimal overlay-like object to verify the
_dismiss helper leaves no exceptions and that nearest token retrieval
works through the public utility function already covered elsewhere.
"""

from __future__ import annotations

import types

from gui.design.loader import load_tokens
from gui.design.color_picker_utils import nearest_color_token


def test_nearest_color_token_basic():
    tokens = load_tokens()
    key, hex_val, dist = nearest_color_token("#3d8bfd", tokens)
    assert key.endswith("accent.primary")
    assert hex_val.lower() == "#3d8bfd"
    assert dist == 0


def test_nearest_color_token_offset():
    tokens = load_tokens()
    key, hex_val, dist = nearest_color_token("#3d90fd", tokens)
    assert key.endswith("accent.primary")
    assert dist > 0


def test_overlay_dismiss_fallback():
    # Import lazily in case Qt not fully available in headless env.
    from gui.views.color_picker_overlay import ColorPickerOverlay  # type: ignore

    try:
        ov = ColorPickerOverlay(parent=None)  # parentless acceptable for logic path
        # Force internal token to simulate click copying scenario
        ov._last_token_key = "color.accent.primary"
        ov._dismiss()  # Should not raise
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"Dismiss raised unexpectedly: {exc}")
