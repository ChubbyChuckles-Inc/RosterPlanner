from gui.views.split_team_compare_view import SplitTeamCompareView
from PyQt6.QtWidgets import QApplication
import sys


def test_split_view_divider_styling(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    view = SplitTeamCompareView()
    qtbot.addWidget(view)
    splitter = view.splitter
    assert splitter.objectName() == "compareSplitter"
    # Basic sanity: QSS applied contains handle selector
    assert "compareSplitter::handle" in splitter.styleSheet()
