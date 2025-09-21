from gui.services.error_handling_service import ErrorHandlingService
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.logging_service import LoggingService
import logging


def test_handle_exception_records_and_limits():
    svc = ErrorHandlingService(capacity=2)
    try:
        raise ValueError("boom1")
    except ValueError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    try:
        raise RuntimeError("boom2")
    except RuntimeError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    try:
        raise KeyError("boom3")
    except KeyError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    errs = svc.recent_errors()
    # capacity 2 keeps only last two
    assert len(errs) == 2
    assert errs[-1].exc_type is KeyError
    assert errs[0].exc_type is RuntimeError


def test_logging_integration():
    logging_svc = LoggingService(capacity=5)
    logging_svc.attach_root()
    svc = ErrorHandlingService(logger=logging.getLogger("test"))
    try:
        raise AssertionError("failure")
    except AssertionError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    # Ensure at least one record in logging service filtered by name
    recs = logging_svc.filter(name_contains="test")
    assert any("Uncaught exception" in r.message for r in recs)


def test_event_bus_emission():
    bus = EventBus()
    received = []
    bus.subscribe(GUIEvent.UNCAUGHT_EXCEPTION, lambda evt: received.append(evt.payload))
    svc = ErrorHandlingService(event_bus=bus)
    try:
        raise RuntimeError("hazard")
    except RuntimeError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    assert received and received[0]["type"] == "RuntimeError"
    assert received[0]["message"] == "hazard"
