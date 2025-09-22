from gui.services.club_data_service import ClubDataService


class _Team:
    def __init__(self, id: str, division_id: str):
        self.id = id
        self.division_id = division_id


class _Player:
    def __init__(self, id: str, team_id: str, live_pz):
        self.id = id
        self.team_id = team_id
        self.live_pz = live_pz


class _TeamsRepo:
    def __init__(self, teams):
        self._teams = teams

    def list_teams_for_club(self, club_id: str):  # pragma: no cover - simple
        return [t for t in self._teams if t.id.startswith(club_id)]


class _PlayersRepo:
    def __init__(self, players):
        self._players = players

    def list_players_for_team(self, team_id: str):  # pragma: no cover - simple
        return [p for p in self._players if p.team_id == team_id]


def test_club_data_service_basic():
    teams = [
        _Team("c1_t1", "1 Bezirksliga Erwachsene"),
        _Team("c1_t2", "1 Stadtliga Jugend 15"),
        _Team("c1_t3", "1 Bezirksliga Erwachsene"),
    ]
    players = [
        _Player("p1", "c1_t1", 1400),
        _Player("p2", "c1_t1", None),
        _Player("p3", "c1_t2", 1200),
        _Player("p4", "c1_t3", 1500),
    ]
    svc = ClubDataService(teams=_TeamsRepo(teams), players=_PlayersRepo(players))
    stats = svc.load_club_stats("c1")
    assert stats.total_teams == 3
    assert stats.erwachsene_teams == 2
    assert stats.jugend_teams == 1
    assert stats.avg_live_pz is not None and 1360 <= stats.avg_live_pz <= 1370
    assert stats.active_teams == 3
    assert stats.inactive_teams == 0
    div_names = [d.division for d in stats.teams]
    assert any("Jugend" in d for d in div_names)
