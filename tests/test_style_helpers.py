from __future__ import annotations

import types

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

from gui.utils.style_helpers import ensure_styled_background


def test_ensure_styled_background_sets_flags():
    app = QApplication.instance() or QApplication([])
    _ = app
    widget = QWidget()
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    widget.setAutoFillBackground(False)

    ensure_styled_background(widget)

    assert widget.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert widget.autoFillBackground()


def test_database_panel_sets_styled_background(monkeypatch):
    app = QApplication.instance() or QApplication([])
    _ = app
    from gui.views import database_panel

    dummy_services = types.SimpleNamespace(try_get=lambda *_: None)
    monkeypatch.setattr(database_panel, "_services", dummy_services)

    panel = database_panel.DatabasePanel()
    try:
        assert panel.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        assert panel.autoFillBackground()
    finally:
        panel.deleteLater()


def test_ingestion_lab_panel_sets_styled_background(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    _ = app
    from gui.views.ingestion_lab import panel as ingestion_panel

    dummy_services = types.SimpleNamespace(try_get=lambda *_: None)
    monkeypatch.setattr(ingestion_panel, "_services", dummy_services)

    panel = ingestion_panel.IngestionLabPanel(str(tmp_path))
    try:
        assert panel.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        assert panel.autoFillBackground()
    finally:
        panel.deleteLater()
