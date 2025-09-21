import importlib
import os
import sys
from pathlib import Path

import pytest

# We import the module normally first
from src.gui.design import reduced_motion as rm


def test_default_state_false():
    # Unless env var set externally the default should be False
    assert rm.is_reduced_motion() is False
    assert rm.motion_scale() == 1.0
    assert rm.adjust_duration(150) == 150


def test_toggle_and_duration():
    rm.set_reduced_motion(True)
    assert rm.is_reduced_motion() is True
    assert rm.motion_scale() == 0.0
    assert rm.adjust_duration(250, minimum_ms=5) == 5

    rm.set_reduced_motion(False)
    assert rm.is_reduced_motion() is False
    assert rm.adjust_duration(250, minimum_ms=5) == 250


def test_motion_scale_fallback_validation():
    with pytest.raises(ValueError):
        rm.motion_scale(0)
    with pytest.raises(ValueError):
        rm.motion_scale(-1)


def test_context_manager_restores_state():
    rm.set_reduced_motion(False)
    with rm.temporarily_reduced_motion(True):
        assert rm.is_reduced_motion() is True
    assert rm.is_reduced_motion() is False

    rm.set_reduced_motion(True)
    with rm.temporarily_reduced_motion(False):
        assert rm.is_reduced_motion() is False
    assert rm.is_reduced_motion() is True


def test_context_manager_exception_safety():
    rm.set_reduced_motion(False)
    try:
        with rm.temporarily_reduced_motion(True):
            assert rm.is_reduced_motion() is True
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert rm.is_reduced_motion() is False


def test_env_var_bootstrap(monkeypatch, tmp_path):
    # Simulate fresh interpreter import with env var forcing reduced motion
    monkeypatch.setenv("APP_PREFER_REDUCED_MOTION", "1")

    # Reloading in place won't re-run module top-level env read unless we
    # remove from sys.modules and import again.
    if "src.gui.design.reduced_motion" in sys.modules:
        del sys.modules["src.gui.design.reduced_motion"]
    import src.gui.design.reduced_motion as fresh

    assert fresh.is_reduced_motion() is True
    assert fresh.motion_scale() == 0.0

    # cleanup - restore environment impact by disabling
    fresh.set_reduced_motion(False)


def test_negative_duration_clamped():
    rm.set_reduced_motion(False)
    assert rm.adjust_duration(-50) == 0  # clamped
    rm.set_reduced_motion(True)
    assert rm.adjust_duration(-50, minimum_ms=10) == 10
