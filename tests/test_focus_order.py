from __future__ import annotations

import pytest

from gui.testing import compute_logical_focus_order, focus_order_names

pytestmark = pytest.mark.skipif(
    True, reason="Focus order tests require PyQt-enabled environment; placeholder logic-only skip"
)


def test_focus_order_placeholder():  # This will be skipped until PyQt test harness added
    assert True
