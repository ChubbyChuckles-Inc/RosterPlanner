"""Tests for error state visual taxonomy (Milestone 0.19)."""

from gui.design.error_states import list_error_states, get_error_state, ErrorState
import pytest


def test_registry_contents():
    states = list_error_states()
    # Expect three canonical entries
    ids = [s.id for s in states]
    assert ids == ["soft-warning", "blocking-error", "critical-failure"]

    # Ensure ordering by level ascending
    levels = [s.level for s in states]
    assert levels == sorted(levels)


def test_unique_levels_and_blocking_flags():
    states = list_error_states()
    levels = [s.level for s in states]
    assert len(levels) == len(set(levels)), "Levels should be unique for deterministic ordering"
    # Blocking flags escalate (once True stays True at higher severity)
    blocking_progression = [s.blocking for s in states]
    assert blocking_progression == [False, True, True]


def test_lookup_by_id():
    s = get_error_state("blocking-error")
    assert isinstance(s, ErrorState)
    assert s.blocking is True
    assert s.persistent is True
    assert s.color_role.startswith("alert-")


def test_unknown_id_raises():
    with pytest.raises(KeyError):
        get_error_state("missing")
