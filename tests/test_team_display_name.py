from gui.models import TeamEntry


def test_team_entry_display_name_with_club():
    t = TeamEntry(team_id="t1", name="1. Erwachsene", division="Bezirksliga", club_name="SSV Stötteritz")
    assert "SSV Stötteritz" in t.display_name
    assert "1. Erwachsene" in t.display_name


def test_team_entry_display_name_without_club():
    t = TeamEntry(team_id="t2", name="1. Erwachsene", division="Bezirksliga")
    assert t.display_name == "1. Erwachsene"