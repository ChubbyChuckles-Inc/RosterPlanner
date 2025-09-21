from gui.services.repo_injection import register_repo, get_repo, inject_repos, repo_key
from gui.services.service_locator import services, ServiceNotFoundError
import pytest


class FakePlayerRepo:
    def __init__(self, players):
        self.players = players


def test_register_and_get_repo():
    repo = FakePlayerRepo(["A"])
    register_repo("player", repo)
    loaded = get_repo("player", FakePlayerRepo)
    assert loaded.players == ["A"]


def test_type_mismatch():
    register_repo("team", {"teams": []})
    with pytest.raises(TypeError):
        get_repo("team", FakePlayerRepo)


def test_inject_repos_context_temporarily_overrides():
    base_repo = FakePlayerRepo(["Base"])
    register_repo("player", base_repo)
    with inject_repos(player=FakePlayerRepo(["Temp"])):
        assert get_repo("player").players == ["Temp"]
    assert get_repo("player").players == ["Base"]


def test_inject_repos_ephemeral():
    with inject_repos(stats=FakePlayerRepo(["S"])):
        assert get_repo("stats").players == ["S"]
    with pytest.raises(ServiceNotFoundError):
        services.get(repo_key("stats"))
