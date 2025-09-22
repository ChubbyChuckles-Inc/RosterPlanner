from gui.views.team_detail_view import TeamDetailView
from gui.models import TeamRosterBundle, TeamEntry, PlayerEntry, MatchDate


def test_build_player_hover_text():
    view = TeamDetailView()
    p_with = PlayerEntry(team_id="t1", name="Alice", live_pz=1510)
    p_without = PlayerEntry(team_id="t1", name="Bob", live_pz=None)
    txt_with = view._build_player_hover_text(p_with)
    txt_without = view._build_player_hover_text(p_without)
    assert "Alice" in txt_with and "1510" in txt_with
    assert "Bob" in txt_without and "—" in txt_without
