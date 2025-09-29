import os
import sys

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.services.service_locator import services
from gui.views.database_panel import DatabasePanel


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(sys.argv[:1])


class _FakeSafetyService:
    def __init__(self, enabled: bool = False) -> None:
        self.state = enabled
        self.set_calls: list[bool] = []

    def admin_enabled(self) -> bool:
        return self.state

    def set_admin_enabled(self, enabled: bool) -> bool:
        changed = self.state != enabled
        self.state = enabled
        self.set_calls.append(enabled)
        return changed


@pytest.fixture
def qt_app() -> QApplication:
    app = _app()
    yield app


def test_database_panel_defaults_to_read_only(qt_app: QApplication):
    fake_service = _FakeSafetyService(False)
    with services.override_context(database_safety_service=fake_service):
        panel = DatabasePanel()
        assert panel.is_admin_mode() is False
        assert panel.admin_toggle.isChecked() is False
        assert fake_service.set_calls == []
        assert "READ-ONLY" in panel.banner.text()
        assert panel.admin_actions.isHidden() is True
        assert panel.admin_notice.isHidden() is False


def test_database_panel_toggle_enables_admin_mode(qt_app: QApplication):
    fake_service = _FakeSafetyService(False)
    with services.override_context(database_safety_service=fake_service):
        panel = DatabasePanel()
        panel.admin_toggle.setCheckState(Qt.CheckState.Checked)
        qt_app.processEvents()
        assert panel.is_admin_mode() is True
        assert fake_service.state is True
        assert fake_service.set_calls[-1] is True
        assert panel.admin_actions.isHidden() is False
        assert panel.admin_notice.isHidden() is True
        assert "ADMIN" in panel.banner.text()


def test_database_panel_respects_persisted_admin_state(qt_app: QApplication):
    fake_service = _FakeSafetyService(True)
    with services.override_context(database_safety_service=fake_service):
        panel = DatabasePanel()
        assert panel.is_admin_mode() is True
        assert panel.admin_toggle.isChecked() is True
        assert panel.admin_actions.isHidden() is False
        assert panel.admin_notice.isHidden() is True
        assert "ADMIN" in panel.banner.text()
