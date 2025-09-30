from __future__ import annotations

from typing import Generator

import pytest
from PyQt6.QtWidgets import QApplication

from gui.services.service_locator import services
from gui.views.database_panel import DatabasePanel


class _StubTheme:
    def colors(self) -> dict[str, str]:
        return {
            "background.secondary": "#202530",
            "surface.card": "#1a1f29",
            "surface.sunken": "#151922",
            "text.primary": "#F1F3F5",
            "text.muted": "#A6B0BF",
            "border.medium": "#3F4C63",
            "accent.base": "#4DA3FF",
        }


@pytest.fixture
def qt_app() -> Generator[QApplication, None, None]:
    app = QApplication.instance() or QApplication([])
    yield app


def test_database_panel_theme_applies_stylesheet(qt_app: QApplication) -> None:
    theme = _StubTheme()
    with services.override_context(theme_service=theme):
        panel = DatabasePanel()
        qt_app.processEvents()
    try:
        stylesheet = panel.styleSheet()
        assert "#databasePanel QPlainTextEdit" in stylesheet
        assert "#databasePanel QTableWidget" in stylesheet
        assert "#databasePanel QComboBox" in stylesheet
    finally:
        panel.deleteLater()
