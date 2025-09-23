import pytest
from PyQt6.QtWidgets import QApplication
import sys
from gui.views.club_detail_view import ClubDetailView
from gui.views.html_source_view import HtmlSourceView
from gui.services.html_diff import HtmlDiffService, HtmlSource
from gui.components.empty_state import empty_state_registry


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_registry_has_new_html_template():
    keys = set(empty_state_registry.all_keys())
    assert "no_html_source" in keys


def test_club_detail_view_empty_state_visible_when_no_teams():
    view = ClubDetailView()
    # Trigger population path explicitly
    view.set_teams([])
    # Empty state considered active if table row count is 0
    assert view.div_table.rowCount() == 0
    # Populate with one team -> empty state hidden (row count >0)
    from gui.models import TeamEntry

    view.set_teams([TeamEntry(team_id="t1", name="A", division="Div 1")])
    assert view.div_table.rowCount() == 1
    # Clear teams again
    view.set_teams([])
    assert view.div_table.rowCount() == 0


def test_html_source_view_empty_state_before_load(tmp_path):
    diff_service = HtmlDiffService(str(tmp_path))
    view = HtmlSourceView(diff_service)
    # Simulate mode apply without source should keep tabs hidden
    view._apply_mode()
    assert not view.tabs.isVisible()
    # Create fake source file
    p = tmp_path / "team_roster_sample.html"
    p.write_text("<html><body><p>Test</p></body></html>")
    src = HtmlSource(
        label="sample",
        current_path=p,
        previous_path=None,
        current_text=p.read_text(),
        previous_text=None,
    )
    view.set_html_source(src)
    # After setting source, expect source text present
    assert "Test" in view.txt_source.toPlainText()
