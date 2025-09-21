from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from gui.testing import hash_image_bytes, compare_or_update_baseline, VisualDiffResult

pytestmark = pytest.mark.usefixtures("_clean_visual_baselines")

BASELINE_ROOT = Path("tests/_visual_baseline")


@pytest.fixture(name="_clean_visual_baselines")
def _clean_visual_baselines_fixture():
    # Ensure test isolation (remove temp dir for this specific test module only)
    if BASELINE_ROOT.exists():
        # Only clear subdir for our test name to avoid wiping future extended baselines
        target = BASELINE_ROOT / "test_visual_regression"
        if target.exists():
            for p in target.glob("*"):
                p.unlink()
    yield


def test_hash_stable():
    data = b"PNGDATA"  # Shallow check; we only test hashing utility deterministically
    h1 = hash_image_bytes(data)
    h2 = hash_image_bytes(data)
    assert h1 == h2


def test_compare_missing_baseline(tmp_path):
    img = b"fakeimagebytes"
    res = compare_or_update_baseline("test_visual_regression", "case1", img, update=False)
    assert not res.matched
    assert res.baseline_hash is None
    assert res.reason == "Baseline missing"


def test_create_and_match_baseline():
    img = b"image-A"
    create = compare_or_update_baseline("test_visual_regression", "case2", img, update=True)
    assert create.updated and not create.matched
    # Second run (same bytes) should match
    match = compare_or_update_baseline("test_visual_regression", "case2", img, update=False)
    assert match.matched
    assert match.reason == "Hashes match"


def test_update_on_mismatch():
    img1 = b"image-old"
    img2 = b"image-new"
    create = compare_or_update_baseline("test_visual_regression", "case3", img1, update=True)
    assert create.updated
    mismatch = compare_or_update_baseline("test_visual_regression", "case3", img2, update=False)
    assert not mismatch.matched
    assert mismatch.reason == "Hash mismatch"
    updated = compare_or_update_baseline("test_visual_regression", "case3", img2, update=True)
    assert updated.updated and not updated.matched
    assert updated.reason.startswith("Baseline updated")
