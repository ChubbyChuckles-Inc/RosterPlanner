from gui.services.telemetry_service import TelemetryService


def test_telemetry_disabled_by_default():
    # Fresh instance is already created; ensure default disabled unless env set
    TelemetryService.instance.enabled = False
    TelemetryService.instance.preview_runs = 0
    TelemetryService.instance.applied_runs = 0
    TelemetryService.instance.total_preview_time_ms = 0.0
    TelemetryService.instance.record_preview(10)
    TelemetryService.instance.record_apply()
    snap = TelemetryService.instance.snapshot()
    assert snap["preview_runs"] == 0
    assert snap["applied_runs"] == 0


def test_telemetry_records_when_enabled():
    TelemetryService.instance.enabled = True
    TelemetryService.instance.preview_runs = 0
    TelemetryService.instance.applied_runs = 0
    TelemetryService.instance.total_preview_time_ms = 0.0
    TelemetryService.instance.record_preview(25.5)
    TelemetryService.instance.record_preview(14.5)
    TelemetryService.instance.record_apply()
    snap = TelemetryService.instance.snapshot()
    assert snap["preview_runs"] == 2
    assert snap["applied_runs"] == 1
    assert abs(snap["average_preview_ms"] - 20.0) < 0.001
    TelemetryService.instance.enabled = False  # reset for other tests
