import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.document_area import DocumentArea


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
