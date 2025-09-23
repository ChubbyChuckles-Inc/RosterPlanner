import os
import json
from PyQt6.QtCore import QCoreApplication, QTimer

from gui.workers import LandingLoadWorker
from config import settings


def run_worker(worker_cls, *args, **kwargs):
    app = QCoreApplication.instance() or QCoreApplication([])
    QTimer.singleShot(9000, app.quit)
    result_container = {}
    w = worker_cls(*args, **kwargs)

    def _finished(teams, error):
        result_container["teams"] = teams
        result_container["error"] = error
        app.quit()

    w.finished.connect(_finished)  # type: ignore
    w.start()
    app.exec()
    return result_container["teams"], result_container["error"]


def test_tracking_state_divisions_fallback(monkeypatch, tmp_path):
    # Create data dir with tracking JSON that includes divisions + teams but no sqlite ingestion
    data_dir = tmp_path / "data"
    os.makedirs(data_dir, exist_ok=True)
    tracking_path = data_dir / "match_tracking.json"
    payload = {
        "last_scrape": "2025-09-22T12:34:56",
        "divisions": {
            "1. Bezirksliga Erwachsene": {
                "name": "1. Bezirksliga Erwachsene",
                "teams": [
                    {
                        "id": "team-1",
                        "name": "SSV Stötteritz 1",
                        "division_name": "1. Bezirksliga Erwachsene",
                    }
                ],
            }
        },
        "upcoming_matches": [],
    }
    tracking_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    teams, error = run_worker(LandingLoadWorker, club_id=2294, season=2025)
    assert error == ""
    assert len(teams) == 1
    assert teams[0].division == "1. Bezirksliga Erwachsene"
