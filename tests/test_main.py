import pytest

from src.main import main


def test_main(capsys: "pytest.CaptureFixture[str]") -> None:
    """Test for the Entry point for the project."""
    main()
    captured = capsys.readouterr()
    assert captured.out == "Hello from project-template!\n"


def test_build_roster_link_distinct_ids():
    from parsing import club_parser

    link = club_parser.build_roster_link("129868", "20337")
    assert "L2P=20337" in link
    assert "L3P=129868" in link
    assert "Page=Vorrunde" in link
