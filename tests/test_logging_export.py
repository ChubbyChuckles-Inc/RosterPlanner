import json, os, tempfile
from gui.services.logging_service import LoggingService


def make_service():
    svc = LoggingService(capacity=10)
    svc.attach_root()
    return svc


def test_export_jsonl_basic():
    svc = make_service()
    import logging

    logging.getLogger("alpha").info("hello world")
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        written = svc.export_jsonl(path)
        assert written == 1
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["message"] == "hello world"
        assert obj["name"] == "alpha"
        assert obj["level"] == "INFO"
    finally:
        os.remove(path)


def test_export_jsonl_filters_and_append():
    svc = make_service()
    import logging

    log_a = logging.getLogger("alpha")
    log_b = logging.getLogger("beta")
    log_a.debug("dbg hidden if level=INFO")
    log_a.info("info1")
    log_b.warning("warn1")
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        # first export only INFO and above with name filter
        written1 = svc.export_jsonl(path, level="INFO", name_contains="alpha")
        assert written1 == 1
        # append all WARNING+ regardless of name
        written2 = svc.export_jsonl(path, level="WARNING", append=True)
        assert written2 == 1  # only beta warning qualifies
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["message"] == "info1"
        assert second["message"] == "warn1"
    finally:
        os.remove(path)
