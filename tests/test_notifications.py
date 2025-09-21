"""Tests for notification style guidelines (Milestone 0.20)."""

import pytest
from gui.design.notifications import (
    list_notification_styles,
    get_notification_style,
    NotificationStyle,
)


def test_registry_ordering_and_ids():
    styles = list_notification_styles()
    ids = [s.id for s in styles]
    # Sorted by stacking_priority ascending then id
    assert ids == ["critical", "error", "warning", "success", "info"]

    priorities = [s.stacking_priority for s in styles]
    assert priorities == sorted(priorities)


def test_lookup_and_fields():
    error_style = get_notification_style("error")
    assert isinstance(error_style, NotificationStyle)
    assert error_style.persistent is True
    assert error_style.default_timeout_ms == 0
    assert error_style.color_role.startswith("alert-")


def test_info_auto_dismiss():
    info_style = get_notification_style("info")
    assert info_style.default_timeout_ms > 0
    assert info_style.persistent is False


def test_unknown_style_raises():
    with pytest.raises(KeyError):
        get_notification_style("bogus")
