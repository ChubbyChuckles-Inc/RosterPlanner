"""Tests for variable font integration helper (Milestone 5.10.25).

Creates a minimal QApplication because some font database queries require an
active application context. If creation fails (headless issues), tests are
skipped to avoid false negatives—the helper itself degrades gracefully.
"""

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase

from gui.design.variable_font import (
    describe_variable_support,
    interpolate_weight,
    variable_font,
    VariableFontSupport,
)

# Ensure QApplication
_app = QApplication.instance()
if _app is None:
    try:  # pragma: no cover - environment dependent
        _app = QApplication([])
    except Exception:  # pragma: no cover
        pytest.skip(
            "QApplication could not be created; skipping variable font tests",
            allow_module_level=True,
        )


def _pick_existing_family() -> str:
    try:
        fams = QFontDatabase.families()  # type: ignore[attr-defined]
    except Exception:
        fams = []
    if not fams:
        return "Sans"  # generic fallback; font creation will still succeed with system default
    for name in ("Segoe UI", "Arial", "Sans Serif", "Calibri"):
        if name in fams:
            return name
    return fams[0]


def test_describe_variable_support_runs():
    fam = _pick_existing_family()
    sup = describe_variable_support(fam)
    assert sup.family == fam
    assert isinstance(sup.weight_range, tuple) and len(sup.weight_range) == 2


def test_interpolate_weight_snaps_when_not_variable():
    sup = VariableFontSupport("Dummy", False, (400, 700))
    assert interpolate_weight(410, sup) in (400, 500)
    assert interpolate_weight(50, sup) == 400
    assert interpolate_weight(900, sup) == 700


def test_variable_font_weight_application():
    fam = _pick_existing_family()
    f = variable_font(fam, weight=525, pixel_size=14)
    assert f.family() == fam
    assert f.pixelSize() == 14
    # Weight will be clamped/interpolated; just ensure it's within reasonable bounds
    assert 100 <= f.weight() <= 900
