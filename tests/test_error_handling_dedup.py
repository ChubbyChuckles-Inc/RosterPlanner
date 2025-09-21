from gui.services.error_handling_service import ErrorHandlingService


def test_dedup_counts_repeated_trace():
    svc = ErrorHandlingService(capacity=10)
    for _ in range(5):
        try:
            raise ValueError("repeat")
        except ValueError as e:
            svc.handle_exception(type(e), e, e.__traceback__)
    groups = svc.dedup_entries()
    assert len(groups) == 1
    g = groups[0]
    assert g.count == 5
    assert g.first.exc_type is ValueError


def test_dedup_disabled_no_grouping():
    svc = ErrorHandlingService(capacity=10)
    svc.enable_dedup(False)
    for _ in range(3):
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            svc.handle_exception(type(e), e, e.__traceback__)
    assert svc.dedup_entries() == []
    # Raw errors still present
    assert len(svc.recent_errors()) == 3


def test_dedup_reenable_starts_fresh():
    svc = ErrorHandlingService(capacity=10)
    try:
        raise KeyError("x1")
    except KeyError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    assert len(svc.dedup_entries()) == 1
    svc.enable_dedup(False)
    svc.enable_dedup(True)
    # New cycle; previous aggregation cleared
    try:
        raise KeyError("x1")
    except KeyError as e:
        svc.handle_exception(type(e), e, e.__traceback__)
    groups = svc.dedup_entries()
    assert len(groups) == 1
    assert groups[0].count == 1
