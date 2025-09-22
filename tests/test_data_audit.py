from gui.services.data_audit import DataAuditService


def test_data_audit_basic(tmp_path):
    # Create fake division folder and files
    div_dir = tmp_path / "1_Bezirksliga_Test"
    div_dir.mkdir()
    (div_dir / "ranking_table_1_Bezirksliga_Test.html").write_text(
        "<html>rank</html>", encoding="utf-8"
    )
    (div_dir / "team_roster_1_Bezirksliga_Test_Alpha_Team_1001.html").write_text(
        "<html>a</html>", encoding="utf-8"
    )
    (div_dir / "team_roster_1_Bezirksliga_Test_Beta_Team_1002.html").write_text(
        "<html>b</html>", encoding="utf-8"
    )

    svc = DataAuditService(str(tmp_path))
    result = svc.run()

    assert result.total_ranking_tables == 1
    assert result.total_team_rosters == 2
    # Division normalized key should match extracted
    assert any(d.division == "1_Bezirksliga_Test" for d in result.divisions)
    div = next(d for d in result.divisions if d.division == "1_Bezirksliga_Test")
    assert div.ranking_table is not None
    assert len(div.team_rosters) == 2
