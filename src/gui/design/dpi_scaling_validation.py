"""Multi-monitor DPI scaling validation utilities (Milestone 0.38).

Purpose:
    Provide a pure-Python validation layer that can assess a set of monitor
    scaling factors (logical DPI scale multipliers) and flag potential
    problems that could degrade GUI visual consistency or cause rendering
    artifacts (e.g., blurry icons due to fractional mismatch, large deltas
    between monitors causing jumpy window transitions).

Design Considerations:
    - This module deliberately avoids importing PyQt6 to stay testable in
      isolation; integration code can supply the scaling factors gathered
      from QScreen instances (using logicalDotsPerInch() / base DPI).
    - We treat scale factors as floats (e.g., 1.0, 1.25, 1.5, 2.0).
    - Validation heuristics are conservative and easily adjustable via
      parameters.

Core Concepts:
    - DpiScaleSample: dataclass representing a single monitor sample.
    - DpiScalingIssue: dataclass representing a detected issue.
    - validate_scaling(samples, ... thresholds ...) returns a result object.

Heuristics Implemented:
    1. Large Delta: If difference between min and max scale exceeds
       `max_delta_allowed` (default 0.75), flag a 'delta-excessive' issue.
    2. Fractional Anomaly: Scale factors with a long fractional part not in
       a recommended set {0.0, 0.25, 0.5, 0.75} produce a 'fractional-anomaly'
       issue (helps catch weird OS reporting like 1.3333).
    3. Inconsistent Pair: Adjacent sorted scales with gap over
       `adjacent_gap_allowed` produce 'adjacent-gap' issue.
    4. Duplicate Redundancy: If there are >1 duplicates of a scale beyond a
       percentage threshold (not harmful, but informational) -> 'redundant'
       optional informational issue (is_info = True).

Public API:
    - DpiScaleSample
    - DpiScalingIssue
    - DpiScalingReport (result container)
    - validate_scaling(samples, max_delta_allowed=0.75, adjacent_gap_allowed=0.5,
                       allowed_fractionals=(0.0, 0.25, 0.5, 0.75),
                       duplicate_info_threshold=0.6)

Edge Cases:
    - Empty sample list -> returns empty report (no issues)
    - Single sample -> only fractional anomaly check runs
    - Negative or zero scale raises ValueError (invalid input)

Testing Strategy:
    - Standard: scales [1.0, 1.25, 1.5] -> no issues
    - Delta excessive: [1.0, 2.0] with default threshold
    - Fractional anomaly: [1.0, 1.3]
    - Adjacent gap: [1.0, 1.8] (gap 0.8 > 0.5)
    - Duplicate redundancy: many repeats of 1.0 (e.g., 4 out of 5 monitors)
    - Empty list
    - Invalid scale (0 or negative) -> raises
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

__all__ = [
    "DpiScaleSample",
    "DpiScalingIssue",
    "DpiScalingReport",
    "validate_scaling",
]


@dataclass(frozen=True)
class DpiScaleSample:
    monitor_id: str
    scale: float  # e.g., 1.0, 1.25, 1.5

    def __post_init__(self):  # type: ignore[override]
        if self.scale <= 0:
            raise ValueError("scale must be positive")
        if not self.monitor_id.strip():
            raise ValueError("monitor_id must be non-empty")


@dataclass(frozen=True)
class DpiScalingIssue:
    code: str
    message: str
    monitors: Tuple[str, ...]
    is_info: bool = False


@dataclass(frozen=True)
class DpiScalingReport:
    samples: Tuple[DpiScaleSample, ...]
    issues: Tuple[DpiScalingIssue, ...]

    def has_errors(self) -> bool:
        return any(not i.is_info for i in self.issues)

    def list_errors(self) -> List[DpiScalingIssue]:
        return [i for i in self.issues if not i.is_info]

    def list_info(self) -> List[DpiScalingIssue]:
        return [i for i in self.issues if i.is_info]


def validate_scaling(
    samples: Iterable[DpiScaleSample],
    *,
    max_delta_allowed: float = 0.75,
    adjacent_gap_allowed: float = 0.5,
    allowed_fractionals: Sequence[float] = (0.0, 0.25, 0.5, 0.75),
    duplicate_info_threshold: float = 0.6,
) -> DpiScalingReport:
    """Validate a collection of DPI scaling samples.

    Parameters
    ----------
    samples: Iterable[DpiScaleSample]
        Monitor scale samples.
    max_delta_allowed: float
        Maximum allowed (max - min) before flagging delta-excessive.
    adjacent_gap_allowed: float
        Maximum gap between adjacent sorted scales before flagging.
    allowed_fractionals: Sequence[float]
        Permitted fractional components (mod 1.0). Others yield anomaly.
    duplicate_info_threshold: float
        If a single scale accounts for > this proportion of monitors and
        there is at least one other distinct scale, flag informational redundancy.
    """
    sam_list = list(samples)
    if not sam_list:
        return DpiScalingReport(samples=tuple(), issues=tuple())

    # Sort by scale
    ordered = sorted(sam_list, key=lambda s: s.scale)

    issues: List[DpiScalingIssue] = []

    # Global delta check
    if len(ordered) > 1:
        delta = ordered[-1].scale - ordered[0].scale
        if delta > max_delta_allowed:
            issues.append(
                DpiScalingIssue(
                    code="delta-excessive",
                    message=f"Scale delta {delta:.2f} exceeds allowed {max_delta_allowed:.2f}",
                    monitors=(ordered[0].monitor_id, ordered[-1].monitor_id),
                )
            )

    # Adjacent gap check
    for a, b in zip(ordered, ordered[1:]):
        gap = b.scale - a.scale
        if gap > adjacent_gap_allowed:
            issues.append(
                DpiScalingIssue(
                    code="adjacent-gap",
                    message=f"Adjacent scale gap {gap:.2f} exceeds {adjacent_gap_allowed:.2f}",
                    monitors=(a.monitor_id, b.monitor_id),
                )
            )

    # Fractional anomaly
    for s in ordered:
        frac = s.scale - int(s.scale)
        # Allow some floating tolerance around known fractionals
        if not any(abs(frac - af) < 0.001 for af in allowed_fractionals):
            issues.append(
                DpiScalingIssue(
                    code="fractional-anomaly",
                    message=f"Unusual fractional component {frac:.3f} in scale {s.scale}",
                    monitors=(s.monitor_id,),
                )
            )

    # Duplicate redundancy info
    counts = {}
    for s in ordered:
        counts[s.scale] = counts.get(s.scale, 0) + 1
    total = len(ordered)
    if len(counts) > 1:
        for scale_val, cnt in counts.items():
            proportion = cnt / total
            if proportion > duplicate_info_threshold:
                monitors = tuple(s.monitor_id for s in ordered if s.scale == scale_val)
                issues.append(
                    DpiScalingIssue(
                        code="redundant",
                        message=f"Scale {scale_val} appears {cnt}x ({proportion:.0%}) of monitors",
                        monitors=monitors,
                        is_info=True,
                    )
                )

    return DpiScalingReport(samples=tuple(ordered), issues=tuple(issues))
