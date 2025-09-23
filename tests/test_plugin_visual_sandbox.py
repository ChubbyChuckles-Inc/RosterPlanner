from gui.views.plugin_visual_sandbox_panel import scan_widget_stylesheet


class DummyWidget:
    def __init__(self, stylesheet: str):
        self._ss = stylesheet

    def styleSheet(self):  # mimic Qt API
        return self._ss


def test_scan_widget_stylesheet_allows_transitional_and_base():
    w = DummyWidget("QWidget { background:#202020; color:#FFFFFF; border:1px solid #3D8BFD; }")
    offenders = scan_widget_stylesheet(w)
    assert offenders == []


def test_scan_widget_stylesheet_detects_new_literal():
    w = DummyWidget("QWidget { background:#AB12EF; }")
    offenders = scan_widget_stylesheet(w)
    assert offenders and offenders[0][0] == "#AB12EF"
