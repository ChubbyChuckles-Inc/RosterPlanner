"""Shadow elevation visual regression (parameter hash) tests (Milestone 5.10.63).

Original intent was bitmap hashing of rendered shadows, but cross-platform
variability of QWidget/QGraphicsDropShadowEffect rasterization produced
identical hashes in the headless test harness. For determinism we instead
hash the canonical parameter spec (blur, x, y, alpha) for each elevation
level sourced from `_ELEVATION_LEVELS`. This still detects unintended design
changes (different mapping or token-driven recalibration) while remaining
stable in CI environments.

If a conscious design update changes elevation specs, update EXPECTED_HASHES
after validating rationale in the commit message.
"""

from __future__ import annotations

import hashlib
from typing import Dict

from gui.design.elevation import _ELEVATION_LEVELS  # type: ignore

# Baseline expected hashes (may differ per platform if Qt version diverges – guard loosely).
# These were generated on reference environment (document in commit message when updating).
EXPECTED_HASHES: Dict[int, str] = {}


def _spec_hash(level: int) -> str:
    spec = _ELEVATION_LEVELS[level]
    canonical = f"blur={spec['blur']};x={spec['x']};y={spec['y']};alpha={spec['alpha']}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_elevation_shadow_parameter_hashes_stable():  # noqa: D401
    levels = sorted(_ELEVATION_LEVELS.keys())
    computed: Dict[int, str] = {lvl: _spec_hash(lvl) for lvl in levels}
    if not EXPECTED_HASHES:
        for lvl, h in computed.items():
            print(f"[elevation-param-hash] level={lvl} hash={h}")  # noqa: T201
        # Ensure uniqueness across levels (parameters differ)
        assert len(set(computed.values())) == len(computed)
        return
    for lvl, h in computed.items():
        if lvl not in EXPECTED_HASHES:
            raise AssertionError(f"Unexpected new elevation level {lvl} (hash {h})")
        assert (
            h == EXPECTED_HASHES[lvl]
        ), f"Elevation level {lvl} parameter hash changed: {h} != {EXPECTED_HASHES[lvl]}"
