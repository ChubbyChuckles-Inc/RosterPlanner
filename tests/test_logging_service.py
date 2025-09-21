import logging
import time
import pytest

from gui.services.logging_service import LoggingService, get_logging_service
from gui.services.service_locator import services
from gui.services.event_bus import EventBus, GUIEvent


@pytest.fixture()
def setup_logging():
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    svc = LoggingService(capacity=5)
    services.register("logging_service", svc, allow_override=True)
    svc.attach_root()
    yield svc, bus
    svc.detach_root()
    services._services.pop("logging_service", None)  # type: ignore[attr-defined]
    services._services.pop("event_bus", None)  # type: ignore[attr-defined]


def test_logging_capture_and_retrieve(setup_logging):
    svc, bus = setup_logging
    logging.getLogger("alpha").info("Hello World")
    time.sleep(0.01)  # ensure record timestamp ordering
    recents = svc.recent()
    assert any(e.message == "Hello World" for e in recents)


def test_logging_capacity_eviction(setup_logging):
    svc, _ = setup_logging
    for i in range(10):
        logging.getLogger("cap").info("M%d", i)
    recents = svc.recent()
    assert len(recents) == 5  # capacity
    assert recents[0].message.endswith("5")  # first retained after evictions


def test_logging_filtering(setup_logging):
    svc, _ = setup_logging
    logging.getLogger("core.db").debug("SQL start")
    logging.getLogger("core.http").info("GET /teams")
    info_only = svc.filter(level="INFO")
    assert all(e.level == "INFO" for e in info_only)
    http = svc.filter(name_contains="http")
    assert http and all("http" in e.name for e in http)


def test_logging_event_emission(setup_logging):
    svc, bus = setup_logging
    payloads = []
    bus.subscribe(GUIEvent.LOG_RECORD_ADDED, lambda evt: payloads.append(evt.payload))
    logging.getLogger("evt").warning("Something happened")
    assert payloads and payloads[-1]["level"] == "WARNING"
