from gui.app.timing import TimingLogger
import json
import os
import tempfile


def test_timing_logger_basic_phases():
    t = TimingLogger()
    with t.measure("phase_one"):
        pass
    with t.measure("phase_two"):
        pass
    t.stop()
    data = t.as_dict()
    assert data["total_duration"] >= 0
    names = [e["name"] for e in data["events"]]
    assert names == ["phase_one", "phase_two"]
    assert all(e["duration"] >= 0 for e in data["events"])


def test_timing_logger_json_export(monkeypatch):
    t = TimingLogger()
    with t.measure("phase"):
        pass
    t.stop()
    # Simulate bootstrap export logic
    path = os.path.join(tempfile.gettempdir(), "timing_export_test.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(t.as_dict(), f)
    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert "events" in loaded and loaded["events"][0]["name"] == "phase"
