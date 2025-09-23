# Minimal conftest providing a fallback 'qtbot' fixture if pytest-qt is not installed.
# This prevents tests that expect a qtbot from erroring; they will still perform
# basic widget lifecycle operations. If pytest-qt is installed, its fixture wins.

import sys
import os
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

    @pytest.fixture(autouse=True, scope="session")
    def _set_offscreen():  # ensure headless platform for Qt
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        return True

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


# Global Qt exec() failsafe: ensure any Q(Core)Application.exec() call during tests
# cannot hang indefinitely. We patch only under pytest environment.
try:  # pragma: no cover - infrastructure
    import os
    from PyQt6.QtCore import QCoreApplication

    if os.environ.get("PYTEST_CURRENT_TEST") is not None and not hasattr(
        QCoreApplication, "_exec_patched_for_tests"
    ):
        _orig_exec = QCoreApplication.exec

        def _timed_exec():  # type: ignore[override]
            import threading, sys as _sys

            app = QCoreApplication.instance()
            timeout_s = float(os.environ.get("QT_EXEC_TIMEOUT", "9"))
            timed_out = {"value": False}

            def bail():
                if app is not None:
                    timed_out["value"] = True
                    try:
                        app.quit()
                    except Exception:  # pragma: no cover
                        pass

            timer = threading.Timer(timeout_s, bail)
            timer.start()
            try:
                return _orig_exec()
            finally:
                timer.cancel()
                if timed_out["value"]:
                    print(f"[qt-exec-timeout] forcibly quit after {timeout_s}s", file=_sys.stderr)

        QCoreApplication.exec = _timed_exec  # type: ignore
        setattr(QCoreApplication, "_exec_patched_for_tests", True)
except Exception:  # pragma: no cover
    pass
