from pathlib import Path

import pytest

from gui.ingestion.fixture_importer import (
    FixtureImportError,
    FIXTURE_SUBDIR,
    prepare_fixture_filename,
    save_html_fixture,
)


def test_prepare_fixture_filename_unique(tmp_path: Path) -> None:
    base = tmp_path
    first = prepare_fixture_filename(base, "Team Card")
    assert first.name == "team-card.html"
    first.write_text("<div>One</div>", encoding="utf-8")
    second = prepare_fixture_filename(base, "Team Card")
    assert second.name == "team-card-1.html"
    # Ensure nested directory path is inside fixtures
    assert first.parent == base / FIXTURE_SUBDIR
    assert second.parent == base / FIXTURE_SUBDIR


def test_save_html_fixture_writes_file(tmp_path: Path) -> None:
    result = save_html_fixture(tmp_path, "<div>hello</div>", filename="Roster")
    assert result.path.read_text(encoding="utf-8").endswith("</div>\n")
    assert result.created is True


def test_save_html_fixture_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(FixtureImportError):
        save_html_fixture(tmp_path, "   ")
