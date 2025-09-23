"""Spring motion helper (Milestone 5.10.27).

Provides a small, dependency-free utility to generate normalized progress
samples for a damped spring curve that can be used to approximate a spring
physics based easing option for micro-interactions and component transitions.

Design Goals:
 - Headless/test friendly (no Qt imports)
 - Deterministic sampling (fixed timestep @ 60 FPS default)
 - Support common parameter trio: stiffness (k), damping (c), mass (m)
 - Auto-derive an approximate duration when caller does not specify,
   by simulating until the remaining energy / displacement is below
   a threshold.
 - Respect global reduced motion preference (collapses to linear ramp).

Public API:
 - SpringParams dataclass
 - spring_samples(params, fps=60, max_ms=1000, settle_epsilon=0.001) -> list[float]
 - critical_damping(stiffness, mass) -> float
 - is_overshooting(samples) -> bool

Simplified Physics Model:
We numerically integrate the second order ODE: m * x'' + c * x' + k * x = 0
with initial conditions x(0) = 1 (displacement), v(0) = 0, solving for the
normalized progress p(t) = 1 - x(t). The solution is computed via a basic
explicit Euler integration that is sufficient for short UI animations.
We clamp overshoot settling once |x| < settle_epsilon and |v| < settle_epsilon.

Accuracy Notes:
This is not intended for high precision physics—visual plausibility and
repeatability are prioritized. Future improvements could swap integration
method (e.g., RK4) while keeping the public API stable.

Reduced Motion:
When reduced motion is active, returns a 2-sample linear [0.0, 1.0] list.

Test Coverage:
 - Monotonic approach to 1.0 for critically/over damped cases (last value ~1)
 - Overshoot detection for under-damped configuration
 - Reduced motion collapses output length
 - Parameter validation (non-positive mass / fps raises)
 - Duration capping (max_ms) respected

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .reduced_motion import is_reduced_motion

__all__ = [
    "SpringParams",
    "spring_samples",
    "critical_damping",
    "is_overshooting",
]


@dataclass(frozen=True)
class SpringParams:
    stiffness: float = 170.0  # k
    damping: float = 26.0  # c (roughly critically damped for default mass)
    mass: float = 1.0  # m
    initial_displacement: float = 1.0
    initial_velocity: float = 0.0

    def validate(self) -> None:
        if self.stiffness <= 0:
            raise ValueError("stiffness must be > 0")
        if self.damping < 0:
            raise ValueError("damping must be >= 0")
        if self.mass <= 0:
            raise ValueError("mass must be > 0")
        if self.initial_displacement <= 0:
            raise ValueError("initial_displacement must be > 0")


def critical_damping(stiffness: float, mass: float) -> float:
    """Return damping coefficient for critical damping (c = 2 * sqrt(k*m))."""
    if stiffness <= 0 or mass <= 0:
        raise ValueError("stiffness and mass must be > 0")
    import math

    return 2.0 * math.sqrt(stiffness * mass)


def spring_samples(
    params: SpringParams,
    fps: int = 60,
    max_ms: int = 1000,
    settle_epsilon: float = 0.001,
) -> List[float]:
    """Generate normalized progress samples for a damped spring.

    Progress is defined as 1 - displacement (so it starts at 0 and approaches 1).

    Parameters
    ----------
    params: SpringParams
        Spring parameter dataclass.
    fps: int
        Sampling frequency (frames per second). Must be > 0.
    max_ms: int
        Maximum simulation duration in milliseconds (caps runaway cases).
    settle_epsilon: float
        Threshold for both absolute displacement and velocity to consider the
        spring settled.
    """
    params.validate()
    if fps <= 0:
        raise ValueError("fps must be > 0")
    if max_ms <= 0:
        raise ValueError("max_ms must be > 0")
    if is_reduced_motion():  # collapse to linear
        return [0.0, 1.0]

    k = params.stiffness
    c = params.damping
    m = params.mass
    x = params.initial_displacement
    v = params.initial_velocity

    dt = 1.0 / fps
    max_s = max_ms / 1000.0
    t = 0.0
    samples: List[float] = [0.0]

    import math

    # Simple explicit Euler integration (adequate for short UI times)
    while t < max_s:
        # acceleration: a = -(c/m) * v - (k/m) * x
        a = -(c / m) * v - (k / m) * x
        v += a * dt
        x += v * dt
        t += dt
        progress = 1.0 - x  # progress towards rest
        if progress > 1.0 + 2.0:  # extreme runaway guard, should not happen
            break
        samples.append(progress)
        # Settled?
        if abs(x) < settle_epsilon and abs(v) < settle_epsilon and t > 0.0:
            if samples[-1] < 1.0:
                samples[-1] = 1.0  # snap to final
            break
        # Overshoot clamp: if damping large enough and progress decreased beyond 1 with tiny amplitude
        if len(samples) > 3 and math.isclose(samples[-1], 1.0, rel_tol=0.0, abs_tol=settle_epsilon):
            break
    # Ensure final sample exactly 1.0
    if samples[-1] < 1.0:
        samples.append(1.0)
    return samples


def is_overshooting(samples: List[float]) -> bool:
    """Return True if any sample exceeds 1.0 (indicating overshoot)."""
    return any(s > 1.0 for s in samples)
