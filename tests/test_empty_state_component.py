"""Tests for EmptyState component (Milestone 5.10.9 partial).

Focus: registry presence & PlayerDetailView integration toggling visibility.
"""

from gui.components.empty_state import empty_state_registry, EmptyStateWidget
from gui.models import PlayerEntry, PlayerHistoryEntry
from gui.views.player_detail_view import PlayerDetailView

import pytest
from PyQt6.QtWidgets import QApplication
import sys


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_registry_bootstrap_templates():
    keys = set(empty_state_registry.all_keys())
    # Expect core templates registered
    for k in {
        "no_history",
        "no_teams",
        "no_division_rows",
        "generic_error",
        "loading",
        "no_html_source",
    }:
        assert k in keys


def test_empty_state_widget_basic():
    w = EmptyStateWidget("no_history")
    assert w.template_key() == "no_history"
    # Title label should reflect template
    assert "History" in w.title_label.text()


def test_player_detail_empty_state_toggle():
    player = PlayerEntry(team_id="t1", name="Test Player")  # type: ignore[arg-type]
    view = PlayerDetailView(player)
    # Ensure empty state appears when setting empty history explicitly
    view.set_history([])
    assert view.is_empty_state_active()
    # Add history entries -> hide empty state
    hist = [PlayerHistoryEntry(iso_date="2025-09-01", live_pz_delta=5)]  # type: ignore[arg-type]
    view.set_history(hist)
    assert not view.is_empty_state_active()
    # Clear history -> show again
    view.set_history([])
    assert view.is_empty_state_active()
