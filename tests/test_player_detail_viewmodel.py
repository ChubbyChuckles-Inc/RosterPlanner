from gui.viewmodels.player_detail_viewmodel import PlayerDetailViewModel
from gui.models import PlayerEntry, PlayerHistoryEntry


def test_player_detail_viewmodel_empty():
    p = PlayerEntry(team_id="t1", name="Alice")
    vm = PlayerDetailViewModel(p)
    vm.set_history([])
    assert vm.summary.entries == 0
    assert vm.summary.as_text() == "No history data"


def test_player_detail_viewmodel_with_deltas():
    p = PlayerEntry(team_id="t1", name="Bob")
    vm = PlayerDetailViewModel(p)
    history = [
        PlayerHistoryEntry(iso_date="2025-09-01", live_pz_delta=5),
        PlayerHistoryEntry(iso_date="2025-09-08", live_pz_delta=-3),
        PlayerHistoryEntry(iso_date="2025-09-15", live_pz_delta=0),
    ]
    vm.set_history(history)
    assert vm.summary.entries == 3
    assert vm.summary.total_delta == 2
    assert abs(vm.summary.avg_delta - (5 + -3 + 0) / 3) < 1e-6
    txt = vm.summary.as_text()
    assert "total" in txt and "avg" in txt


def test_player_detail_viewmodel_missing_deltas():
    p = PlayerEntry(team_id="t1", name="Cara")
    vm = PlayerDetailViewModel(p)
    history = [
        PlayerHistoryEntry(iso_date="2025-09-01", live_pz_delta=None),
        PlayerHistoryEntry(iso_date="2025-09-08", live_pz_delta=None),
    ]
    vm.set_history(history)
    assert vm.summary.entries == 2
    # No valid deltas -> total 0, avg None
    assert vm.summary.total_delta == 0
    assert vm.summary.avg_delta is None
    assert "delta: 0" in vm.summary.as_text()
