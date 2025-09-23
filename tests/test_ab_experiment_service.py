from gui.services.ab_experiment import (
    ABExperimentService,
    ExperimentDefinition,
)
from pathlib import Path
import os


def test_register_and_deterministic_assignment(tmp_path: Path):
    svc = ABExperimentService(str(tmp_path))
    svc.register(ExperimentDefinition("theme_test", ["A", "B"], weights=[1, 3]))
    a1 = svc.assign("theme_test", "user_alpha")
    a2 = svc.assign("theme_test", "user_alpha")  # cached
    assert a1.variant == a2.variant
    # Determinism across new service instance (persisted)
    svc2 = ABExperimentService(str(tmp_path))
    svc2.register(ExperimentDefinition("theme_test", ["A", "B"], weights=[1, 3]))
    a3 = svc2.assign("theme_test", "user_alpha")
    assert a1.variant == a3.variant


def test_equal_weight_default(tmp_path: Path):
    svc = ABExperimentService(str(tmp_path))
    svc.register(ExperimentDefinition("exp_eq", ["x", "y", "z"]))
    # Just ensure an assignment in valid set
    a = svc.assign("exp_eq", "u1")
    assert a.variant in {"x", "y", "z"}


def test_env_override(tmp_path: Path, monkeypatch):
    svc = ABExperimentService(str(tmp_path))
    svc.register(ExperimentDefinition("exp_force", ["c1", "c2"]))
    monkeypatch.setenv("RP_EXPERIMENT_FORCE_EXP_FORCE", "c2")
    a = svc.assign("exp_force", "any_user")
    assert a.variant == "c2"
    assert a.source == "override"


def test_invalid_forced_variant_raises(tmp_path: Path, monkeypatch):
    svc = ABExperimentService(str(tmp_path))
    svc.register(ExperimentDefinition("exp_bad", ["v1", "v2"]))
    monkeypatch.setenv("RP_EXPERIMENT_FORCE_EXP_BAD", "nope")
    try:
        svc.assign("exp_bad", "u")
    except ValueError as e:
        assert "Forced variant" in str(e)
    else:  # pragma: no cover
        assert False, "Expected ValueError for invalid forced variant"
