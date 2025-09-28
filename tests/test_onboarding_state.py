import pytest

from gui.ingestion.onboarding_coach import (
    mark_onboarding_complete,
    mark_onboarding_skipped,
    mark_onboarding_state,
    should_run_onboarding,
)


def test_should_run_onboarding_initial_pending():
    store: dict[str, str] = {}
    assert should_run_onboarding(store) is True


def test_mark_complete_sets_flag():
    store: dict[str, str] = {}
    mark_onboarding_complete(store)
    assert store["onboarding_state_v1"] == "complete"
    assert should_run_onboarding(store) is False


def test_mark_skip_sets_flag():
    store: dict[str, str] = {}
    mark_onboarding_skipped(store)
    assert store["onboarding_state_v1"] == "skip"
    assert should_run_onboarding(store) is False


def test_invalid_state_raises():
    store: dict[str, str] = {}
    with pytest.raises(ValueError):
        mark_onboarding_state("invalid", store)
