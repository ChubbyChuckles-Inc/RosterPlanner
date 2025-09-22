from gui.services.html_diff import HtmlDiffService
from pathlib import Path


def test_unified_diff_basic(tmp_path: Path):
    base = tmp_path
    (base / "team_roster_demo_A.html").write_text("LINE1\nLINE2\n", encoding="utf-8")
    (base / "team_roster_demo_B.html").write_text("LINE1\nLINE2-mod\n", encoding="utf-8")
    svc = HtmlDiffService(str(base))
    # Simulate later file by touching modification times
    src = svc.find_team_roster_html("demo")
    assert src is not None
    diff = svc.unified_diff(src.previous_text, src.current_text)
    assert "LINE2" in diff
    assert "-" in diff and "+" in diff


def test_find_team_roster_html_none(tmp_path: Path):
    svc = HtmlDiffService(str(tmp_path))
    assert svc.find_team_roster_html("missing") is None
