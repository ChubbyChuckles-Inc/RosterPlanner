from gui.services.telemetry import TelemetryService


def test_telemetry_disabled_noop():
    t = TelemetryService(enabled=False)
    t.increment("parsed", 1)
    assert t.get("parsed") == 0


def test_telemetry_increment_and_snapshot():
    t = TelemetryService(enabled=True)
    t.increment("parsed", 3)
    t.increment("skipped", 1)
    t.increment("parsed", 2)
    snap = t.snapshot()
    assert snap["parsed"] == 5
    assert snap["skipped"] == 1
    t.reset()
    assert t.snapshot() == {}
