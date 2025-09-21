from gui.services.error_handling_service import ErrorHandlingService
from gui.services.logging_service import LoggingService
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.diagnostics import generate_crash_snippet, format_crash_snippet_text
import logging


def test_generate_crash_snippet_basic():
    err_svc = ErrorHandlingService(capacity=10)
    # create two errors (one repeat)
    for _ in range(3):
        try:
            raise ValueError("repeat")
        except ValueError as e:
            err_svc.handle_exception(type(e), e, e.__traceback__)
    try:
        raise RuntimeError("other")
    except RuntimeError as e:
        err_svc.handle_exception(type(e), e, e.__traceback__)

    log_svc = LoggingService(capacity=10)
    log_svc.attach_root()
    logging.getLogger("diag").info("hello")
    logging.getLogger("diag").warning("warn")

    bus = EventBus()
    bus.enable_tracing(True, capacity=5)
    bus.publish(GUIEvent.DATA_REFRESHED, {"a": 1})

    snippet = generate_crash_snippet(
        error_service=err_svc,
        logging_service=log_svc,
        event_bus=bus,
        max_errors=5,
        max_logs=5,
        max_events=5,
    )

    assert "environment" in snippet
    assert len(snippet["errors"]) <= 5
    assert snippet["error_dedup"][0]["count"] >= 3
    assert snippet["schema_version"] == 1
    assert snippet["logs"] and snippet["events"]

    text = format_crash_snippet_text(snippet)
    assert "Crash Reproduction Snippet" in text
    assert "JSON Payload" in text


def test_limits_enforced():
    err_svc = ErrorHandlingService(capacity=50)
    for i in range(20):
        try:
            raise KeyError(i)
        except KeyError as e:
            err_svc.handle_exception(type(e), e, e.__traceback__)
    snippet = err_svc.build_crash_snippet(max_errors=5, max_logs=0, max_events=0)
    assert len(snippet["errors"]) == 5
    assert snippet["logs"] == []
    assert snippet["events"] == []
