from pathlib import Path

from gui.design.spring import (
    SpringParams,
    spring_samples,
    critical_damping,
    is_overshooting,
)
from gui.design.reduced_motion import set_reduced_motion, temporarily_reduced_motion


def test_critical_damping_positive():
    d = critical_damping(100.0, 2.0)
    assert d > 0


def test_spring_samples_basic_convergence():
    params = SpringParams(stiffness=120.0, damping=30.0, mass=1.0)
    samples = spring_samples(params, fps=120, max_ms=800)
    assert samples[0] == 0.0
    assert samples[-1] == 1.0
    # Should converge in reasonable number of samples
    assert len(samples) < 500


def test_spring_samples_overshoot():
    # Lower damping to induce overshoot
    params = SpringParams(stiffness=170.0, damping=5.0, mass=1.0)
    samples = spring_samples(params, fps=60, max_ms=1000)
    assert is_overshooting(samples) is True


def test_reduced_motion_collapses():
    with temporarily_reduced_motion(True):
        params = SpringParams()
        samples = spring_samples(params)
        assert samples == [0.0, 1.0]


def test_validation_errors():
    try:
        SpringParams(stiffness=0).validate()
        assert False, "Expected validation error"
    except ValueError:
        pass
    try:
        SpringParams(stiffness=10, damping=-1).validate()
        assert False, "Expected validation error"
    except ValueError:
        pass
    try:
        SpringParams(stiffness=10, damping=1, mass=0).validate()
        assert False, "Expected validation error"
    except ValueError:
        pass


def test_is_overshooting_detection():
    assert is_overshooting([0.0, 1.02, 1.0]) is True
    assert is_overshooting([0.0, 0.5, 0.9, 1.0]) is False
