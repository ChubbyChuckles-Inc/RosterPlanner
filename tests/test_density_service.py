from __future__ import annotations

import pytest

from gui.app.bootstrap import create_app
from gui.services.service_locator import services
from gui.services.density_service import DensityService


def test_density_service_switch_headless(tmp_path):
    # Bootstrap headless app context
    ctx = create_app(headless=True, data_dir=str(tmp_path))
    dens = services.try_get("density_service")
    assert dens is not None, "DensityService should be registered during bootstrap"
    initial = dens.mode()
    assert initial in ("comfortable", "compact")
    # Switch to the other mode
    target = "compact" if initial == "comfortable" else "comfortable"
    diff = dens.set_mode(target)
    assert dens.mode() == target
    # If tokens have spacing group, diff should reflect changes
    # diff.no_changes should be False when an actual mode switch occurred
    assert hasattr(diff, "no_changes")
    assert diff.no_changes is False
    # Switching again to same mode should yield no changes
    diff2 = dens.set_mode(target)
    assert diff2.no_changes is True


def test_density_service_persistence(tmp_path):
    # First run: set mode to compact, ensure saved
    ctx1 = create_app(headless=True, data_dir=str(tmp_path))
    dens1 = services.get_typed("density_service", DensityService)
    dens1.set_mode("compact")
    # Second run: new bootstrap should read persisted compact mode
    ctx2 = create_app(headless=True, data_dir=str(tmp_path))
    dens2 = services.get_typed("density_service", DensityService)
    assert dens2.mode() == "compact"
