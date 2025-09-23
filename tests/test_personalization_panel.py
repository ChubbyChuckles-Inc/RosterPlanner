from gui.views.personalization_panel import PersonalizationPanel
from gui.design.reduced_motion import is_reduced_motion, set_reduced_motion
from gui.services.theme_service import ThemeService
from gui.services.service_locator import services
from gui.design import load_tokens, ThemeManager
from PyQt6.QtWidgets import QApplication
import sys


def _ensure_theme_service():
    # Register a ThemeService if not present
    if not services.try_get("theme_service"):
        mgr = ThemeManager(load_tokens(), variant="default")  # type: ignore[arg-type]
        svc = ThemeService(manager=mgr, _cached_map=dict(mgr.active_map()))
        services.register("theme_service", svc, allow_override=True)


def test_personalization_panel_toggles(qtbot):
    _ensure_theme_service()
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    panel = PersonalizationPanel()
    qtbot.addWidget(panel)  # type: ignore
    # Initial state should reflect defaults
    assert panel.chk_reduced_motion.isChecked() == is_reduced_motion()
    # Toggle reduced motion
    panel.chk_reduced_motion.setChecked(True)
    assert is_reduced_motion() is True
    panel.chk_reduced_motion.setChecked(False)
    assert is_reduced_motion() is False
    # Toggle high contrast
    panel.chk_high_contrast.setChecked(True)
    svc = services.get_typed("theme_service", ThemeService)
    assert svc.manager.variant == "high-contrast"
    # Reset
    panel._on_reset()
    assert svc.manager.variant == "default"
    assert is_reduced_motion() is False
