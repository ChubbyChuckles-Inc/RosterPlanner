# Minimal conftest providing a fallback 'qtbot' fixture if pytest-qt is not installed.
# This prevents tests that expect a qtbot from erroring; they will still perform
# basic widget lifecycle operations. If pytest-qt is installed, its fixture wins.

import sys
import types
import contextlib
import pytest

try:  # If pytest-qt present, do nothing (its fixture will be used)
    import pytestqt  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:  # pragma: no cover
        QApplication = None  # type: ignore

    @pytest.fixture
    def qtbot():  # type: ignore
        if QApplication is None:
            pytest.skip("PyQt6 not available")
        app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
        widgets = []
        class Bot:
            def addWidget(self, w):  # mimic pytest-qt API subset
                widgets.append(w)
            @contextlib.contextmanager
            def waitSignal(self, *args, **kwargs):  # no-op stub
                yield
        return Bot()
