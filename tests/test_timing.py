from gui.app.bootstrap import create_app


def test_startup_timing_logger_headless():
    ctx = create_app(headless=True)
    timing = ctx.timing
    # Ensure events captured
    names = [e.name for e in timing.events]
    assert "load_design_tokens" in names
    assert "register_services" in names
    # Durations are non-negative
    assert all(e.duration >= 0 for e in timing.events)
    # Total duration should be >= sum of events (allow tiny float diff)
    total_events = sum(e.duration for e in timing.events)
    assert timing.total_duration + 1e-6 >= total_events


def test_timing_service_registration():
    ctx = create_app(headless=True)
    svc_logger = ctx.services.get("startup_timing")
    assert svc_logger is ctx.timing