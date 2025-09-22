from gui.design.elevation import (
    get_shadow_effect,
    apply_elevation_role,
    ElevationRole,
    current_role_level,
)
from PyQt6.QtWidgets import QWidget, QApplication
import sys
import pytest


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    """Ensure a single QApplication instance for the module tests.

    Using module scope prevents creation/destruction churn which sometimes
    leads to hangs in certain PyQt builds when effects are applied without a
    running application context.
    """
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


def test_get_shadow_effect_known_levels():
    eff0 = get_shadow_effect(0)
    eff1 = get_shadow_effect(1)
    eff2 = get_shadow_effect(2)
    assert eff0.blurRadius() <= eff1.blurRadius() <= eff2.blurRadius()
    assert eff0.yOffset() <= eff1.yOffset() <= eff2.yOffset()


def test_get_shadow_effect_out_of_range():
    eff_high = get_shadow_effect(999)
    # Should clamp/fallback to highest defined level
    assert eff_high.blurRadius() > 0


def test_apply_elevation_role_levels():
    w = QWidget()
    apply_elevation_role(w, ElevationRole.FLAT)
    assert w.graphicsEffect() is None
    apply_elevation_role(w, ElevationRole.PRIMARY_DOCK)
    eff = w.graphicsEffect()
    assert eff is not None
    # Now apply floating and ensure blur increases or equals
    prev_blur = eff.blurRadius() if hasattr(eff, "blurRadius") else 0
    apply_elevation_role(w, ElevationRole.FLOATING_DOCK)
    eff2 = w.graphicsEffect()
    assert eff2 is not None
    if hasattr(eff2, "blurRadius"):
        assert eff2.blurRadius() >= prev_blur
    # Mapping sanity
    assert current_role_level(ElevationRole.PRIMARY_DOCK) >= current_role_level(
        ElevationRole.SECONDARY_DOCK
    )
    assert current_role_level(ElevationRole.FLOATING_DOCK) >= current_role_level(
        ElevationRole.PRIMARY_DOCK
    )
