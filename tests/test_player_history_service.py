from gui.services.player_history_service import PlayerHistoryService
from gui.models import PlayerEntry


def test_player_history_service_deterministic_rotation(monkeypatch):
    # Freeze date for deterministic output
    import datetime as _dt

    class _FixedDate(_dt.date):
        @classmethod
        def today(cls):
            return cls(2025, 9, 22)

    monkeypatch.setattr(_dt, "date", _FixedDate)
    player = PlayerEntry(team_id="t1", name="Alice", live_pz=1400)
    svc = PlayerHistoryService(players=None)  # no repo needed for placeholder logic
    result = svc.load_player_history(player)
    assert result.player == player
    assert len(result.entries) == 5
    # Pattern rotation check: base pattern [5,-3,0,4,-2]; name hash rotation must produce deterministic first delta
    first_delta = result.entries[0].live_pz_delta
    assert first_delta in {5, -3, 0, 4, -2}
    # Dates descending weekly order
    iso_dates = [e.iso_date for e in result.entries]
    assert iso_dates == sorted(iso_dates)  # increasing chronological order


def test_player_history_service_no_live_pz():
    player = PlayerEntry(team_id="t1", name="Bob", live_pz=None)
    svc = PlayerHistoryService(players=None)
    result = svc.load_player_history(player)
    assert result.entries == []
