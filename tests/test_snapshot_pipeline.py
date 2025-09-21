"""Tests for snapshot pipeline primitives (Milestone 0.29)."""

from gui.design.snapshot_pipeline import compute_image_hash, capture_bytes_placeholder


def test_compute_image_hash_deterministic():
    data1 = capture_bytes_placeholder(width=2, height=2, color=0x11223344)
    data2 = capture_bytes_placeholder(width=2, height=2, color=0x11223344)
    assert data1 == data2
    h1 = compute_image_hash(data1)
    h2 = compute_image_hash(data2)
    assert h1 == h2


def test_compute_image_hash_variation():
    base = capture_bytes_placeholder(width=2, height=2, color=0x11223344)
    changed = capture_bytes_placeholder(width=2, height=2, color=0x11223345)
    h_base = compute_image_hash(base)
    h_changed = compute_image_hash(changed)
    assert h_base != h_changed
