import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.document_area import DocumentArea


class _DummyTheme:
    def __init__(self, mapping):
        self._mapping = mapping

    def colors(self):  # pragma: no cover - simple accessor
        return dict(self._mapping)


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_document_area_add_and_focus(qtbot):  # qtbot from pytest-qt
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    da = DocumentArea()

    def make_factory(label):
        def _f():
            w = QWidget()
            w.setObjectName(label)
            QLabel(label, parent=w)
            return w

        return _f

    w1 = da.open_or_focus("doc1", "Doc 1", make_factory("one"))
    assert da.has_document("doc1")
    assert da.document_widget("doc1") is w1
    # Opening again focuses existing, not duplicate
    w1b = da.open_or_focus("doc1", "Doc 1", make_factory("one"))
    assert w1b is w1

    w2 = da.open_or_focus("doc2", "Doc 2", make_factory("two"))
    assert w2 is not w1
    assert da.has_document("doc2")


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_document_area_theme_applied(qtbot):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    da = DocumentArea()
    theme = _DummyTheme(
        {
            "background.base": "#101010",
            "background.secondary": "#151515",
            "surface.card": "#181818",
            "text.primary": "#e6e6e6",
            "accent.base": "#3d8bfd",
            "border.medium": "#2a72c1",
            "border.light": "#1a3f6a",
        }
    )
    da.on_theme_changed(theme, [])
    stylesheet = da.styleSheet()
    assert "#documentArea" in stylesheet
    assert "#101010" in stylesheet
    assert "#181818" in stylesheet
