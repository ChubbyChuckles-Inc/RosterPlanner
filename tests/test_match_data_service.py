import datetime as _dt
from types import SimpleNamespace

from gui.services.match_data_service import MatchDataService


class _Match:
    def __init__(
        self, id: str, division_id: str, home_team_id: str, away_team_id: str, iso_date: str
    ):
        self.id = id
        self.division_id = division_id
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id
        self.iso_date = iso_date
        self.home_score = None
        self.away_score = None


class _TeamsRepo:
    def __init__(self, team_map):
        self._team_map = team_map

    def get_team(self, team_id: str):  # pragma: no cover - simple
        return self._team_map.get(team_id)


class _MatchesRepo:
    def __init__(self, matches):
        self._matches = matches

    def list_matches_for_division(self, division_id: str):  # pragma: no cover - simple
        return [m for m in self._matches if m.division_id == division_id]


def _install_repos(monkeypatch, teams_repo, matches_repo):
    # No longer patch sqlite; service accepts direct repo injection.
    return teams_repo, matches_repo


def test_team_match_segmentation(monkeypatch):
    today = _dt.date.today()
    matches = [
        _Match("m1", "d1", "t1", "t2", (today - _dt.timedelta(days=14)).isoformat()),
        _Match("m2", "d1", "t1", "t3", (today - _dt.timedelta(days=1)).isoformat()),
        _Match("m3", "d1", "t2", "t1", (today + _dt.timedelta(days=3)).isoformat()),
        _Match(
            "m4", "d1", "t4", "t5", (today + _dt.timedelta(days=10)).isoformat()
        ),  # unrelated to t1
    ]
    teams_repo = _TeamsRepo(
        {
            "t1": SimpleNamespace(id="t1", division_id="d1"),
            "t2": SimpleNamespace(id="t2", division_id="d1"),
        }
    )
    matches_repo = _MatchesRepo(matches)
    _install_repos(monkeypatch, teams_repo, matches_repo)

    svc = MatchDataService(teams_repo=teams_repo, matches_repo=matches_repo)
    sets = svc.team_matches("t1")
    assert [m.id for m in sets.past] == ["m1", "m2"]
    assert [m.id for m in sets.upcoming] == ["m3"]  # m4 excluded (no team involvement)


def test_division_match_segmentation(monkeypatch):
    today = _dt.date.today()
    matches = [
        _Match("m1", "dX", "t1", "t2", (today - _dt.timedelta(days=7)).isoformat()),
        _Match("m2", "dX", "t3", "t4", (today + _dt.timedelta(days=1)).isoformat()),
        _Match("m3", "dX", "t5", "t6", today.isoformat()),
    ]
    teams_repo = _TeamsRepo({"t1": SimpleNamespace(id="t1", division_id="dX")})
    matches_repo = _MatchesRepo(matches)
    _install_repos(monkeypatch, teams_repo, matches_repo)

    svc = MatchDataService(teams_repo=teams_repo, matches_repo=matches_repo)
    sets = svc.division_matches("dX")
    assert [m.id for m in sets.past] == ["m1"]
    # upcoming includes today+future sorted chronologically
    assert [m.id for m in sets.upcoming] == ["m3", "m2"]
