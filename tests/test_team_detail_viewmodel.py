from gui.viewmodels.team_detail_viewmodel import TeamDetailViewModel
from gui.models import TeamRosterBundle, TeamEntry, PlayerEntry, MatchDate


def make_bundle(player_livepz):
    players = [
        PlayerEntry(team_id="t1", name=f"P{i}", live_pz=v) for i, v in enumerate(player_livepz)
    ]
    matches = [
        MatchDate(iso_date="2025-09-21", display="21.09.2025"),
        MatchDate(iso_date="2025-09-28", display="28.09.2025", time="19:00"),
    ]
    return TeamRosterBundle(
        team=TeamEntry(team_id="t1", name="Team One", division="Div A"),
        players=players,
        match_dates=matches,
    )


def test_viewmodel_summary_with_data():
    vm = TeamDetailViewModel()
    bundle = make_bundle([1500, 1510, None, 1490])
    vm.set_bundle(bundle)
    assert vm.summary.player_count == 4
    assert vm.summary.live_pz_count == 3
    assert abs(vm.summary.avg_live_pz - (1500 + 1510 + 1490) / 3) < 1e-6
    assert "players" in vm.summary.as_text()


def test_viewmodel_summary_no_players():
    vm = TeamDetailViewModel()
    empty_bundle = make_bundle([])
    empty_bundle.players = []
    vm.set_bundle(empty_bundle)
    assert vm.summary.player_count == 0
    assert vm.summary.as_text() == "No players"


def test_viewmodel_summary_no_livepz():
    vm = TeamDetailViewModel()
    bundle = make_bundle([None, None])
    vm.set_bundle(bundle)
    assert vm.summary.player_count == 2
    assert vm.summary.live_pz_count == 0
    assert "no LivePZ data" in vm.summary.as_text()
