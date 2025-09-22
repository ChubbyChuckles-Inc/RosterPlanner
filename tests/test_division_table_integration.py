import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.main_window import MainWindow
from gui.models import TeamEntry


@pytest.fixture(scope="module")
def app():  # pragma: no cover - GUI bootstrap
    import sys

    return QApplication.instance() or QApplication(sys.argv)  # type: ignore


def test_open_division_table_creates_and_updates(app):
    mw = MainWindow()
    division_name = "Test Division"
    mw.open_division_table(division_name)
    # After opening, a document tab should exist with id pattern
    # We rely on document_area API exposed earlier in project.
    doc_ids = [d.doc_id for d in mw.document_area._documents]  # type: ignore[attr-defined]
    assert f"division:{division_name}" in doc_ids
    # Fetch the created view and inspect rows
    view = mw.document_area._widgets_by_id[f"division:{division_name}"].widget  # type: ignore[attr-defined]
    table = view.table
    assert table.rowCount() == 6  # placeholder generator creates 6 rows
    # Open again to force update
    mw.open_division_table(division_name)
    # Row count should remain 6 (idempotent refresh)
    assert table.rowCount() == 6
