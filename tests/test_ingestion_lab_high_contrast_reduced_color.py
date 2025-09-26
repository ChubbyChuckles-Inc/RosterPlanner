import os
import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])

class _DummyMode:
    def __init__(self, active: bool):
        self._active = active
    def is_active(self):
        return self._active


def test_high_contrast_and_reduced_color_properties(qtbot, monkeypatch, tmp_path):
    # Provide dummy services via locator override if available
    from gui.services.service_locator import services
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.html").write_text("<html><body>x</body></html>", encoding="utf-8")

    with services.override_context(high_contrast_mode=_DummyMode(True), reduced_color_mode=_DummyMode(True)):
        panel = IngestionLabPanel(base_dir=str(data_dir))
        qtbot.addWidget(panel)
        # Force styling reapply
        panel._apply_density_and_theme()
        assert panel.property("highContrast") == "1"
        assert panel.property("reducedColor") == "1"
        ss = panel.styleSheet()
        # Expect high contrast overrides applied
        assert "background:#000000" in ss or "background: #000000" in ss

    # Now test with neither active to ensure properties reset
    with services.override_context(high_contrast_mode=_DummyMode(False), reduced_color_mode=_DummyMode(False)):
        panel2 = IngestionLabPanel(base_dir=str(data_dir))
        qtbot.addWidget(panel2)
        panel2._apply_density_and_theme()
        assert panel2.property("highContrast") in ("0", None)
        assert panel2.property("reducedColor") in ("0", None)
