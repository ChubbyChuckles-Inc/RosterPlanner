from gui.views.html_source_view import HtmlSourceView
from gui.services.html_diff import HtmlDiffService, HtmlSource
from pathlib import Path
from PyQt6.QtWidgets import QApplication
import sys


class DummySource(HtmlSource):  # pragma: no cover - simple struct extension
    pass


def test_html_source_view_population(qtbot, tmp_path: Path):  # type: ignore
    # Ensure a QApplication is instantiated early (fallback qtbot may not yet)
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    svc = HtmlDiffService(str(tmp_path))
    view = HtmlSourceView(svc)
    qtbot.addWidget(view)
    src = HtmlSource(
        label="team_roster_demo_X.html",
        current_path=tmp_path / "team_roster_demo_X.html",
        previous_path=None,
        current_text="<html>Current</html>",
        previous_text=None,
    )
    view.set_html_source(src)
    assert "Current" in view.txt_source.toPlainText()
    assert "no previous" in view.txt_diff.toPlainText().lower()
