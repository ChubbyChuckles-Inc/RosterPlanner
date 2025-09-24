"""Rebuild Progress Dialog (Milestone 3.8.1)

Provides a modal dialog that runs the enhanced database rebuild in a worker
thread while emitting progress updates. This is an initial minimal
implementation; future milestones may integrate cancellation and richer
logging.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QLabel, QProgressBar, QPushButton
import sqlite3
from pathlib import Path
from typing import Optional

from db.rebuild import rebuild_database_with_progress, RebuildProgressEvent, RebuildPhase
from gui.components.chrome_dialog import ChromeDialog


class _RebuildWorker(QThread):  # pragma: no cover - Qt thread execution path
    progress_event = pyqtSignal(object)
    finished_success = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, db_path: str, html_root: str):
        super().__init__()
        self._db_path = db_path
        self._html_root = html_root

    def run(self):
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA foreign_keys=ON")

            def _cb(evt: RebuildProgressEvent):
                self.progress_event.emit(evt)

            report = rebuild_database_with_progress(conn, self._html_root, progress=_cb)
            try:
                conn.close()
            except Exception:
                pass
            self.finished_success.emit(report)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class RebuildProgressDialog(ChromeDialog):  # pragma: no cover - GUI component
    def __init__(self, db_path: str, html_root: str, parent=None):
        super().__init__(parent, title="Rebuild Database")
        self.resize(420, 160)
        self._label = QLabel("Starting...")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._close_btn = QPushButton("Close")
        self._close_btn.setEnabled(False)
        lay = self.content_layout()
        lay.addWidget(self._label)
        lay.addWidget(self._bar)
        lay.addWidget(self._close_btn)
        self._close_btn.clicked.connect(self.close)

        self._worker = _RebuildWorker(db_path, html_root)
        self._worker.progress_event.connect(self._on_progress)
        self._worker.finished_success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        # Chrome already applied

    def _on_progress(self, evt: RebuildProgressEvent):
        self._label.setText(evt.message)
        self._bar.setValue(evt.percent)
        if evt.phase == RebuildPhase.ERROR:
            self._close_btn.setEnabled(True)

    def _on_success(self, report):
        # IngestReport exposes 'files' list; no 'ingested_files' attribute.
        try:
            total = len(getattr(report, "files", []))
        except Exception:
            total = 0
        self._label.setText(f"Rebuild complete: {total} files")
        self._bar.setValue(100)
        self._close_btn.setEnabled(True)

    def _on_failed(self, err: str):
        self._label.setText(f"Failed: {err}")
        self._close_btn.setEnabled(True)


__all__ = ["RebuildProgressDialog"]
