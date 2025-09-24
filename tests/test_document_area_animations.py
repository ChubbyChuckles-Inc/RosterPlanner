"""Tests for animated tab open/close transitions (Milestone 5.10.58)."""

from __future__ import annotations
import os
from PyQt6.QtWidgets import QApplication
from gui.views.document_area import DocumentArea


def test_tab_open_close_animation(monkeypatch):
    app = QApplication.instance() or QApplication([])
    # Force test + motion enabled fast path
    monkeypatch.setenv("RP_TEST_MODE", "1")
    da = DocumentArea()
    created = da.open_or_focus("doc:1", "One", lambda: DocumentArea())
    assert da.has_document("doc:1")
    # Trigger close through context method
    idx = da._doc_index["doc:1"]  # type: ignore
    da._close_tab(idx)
    # Process events to let 5ms animation finish
    from PyQt6.QtCore import QCoreApplication

    for _ in range(50):
        QCoreApplication.processEvents()
    assert not da.has_document("doc:1")
