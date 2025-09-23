import time

from gui.design.scroll_linked import (
    ScrollEffectConfig,
    compute_scroll_effect,
    should_apply_scroll_effect,
    reset_scroll_effect_perf_counters,
)
from gui.design.reduced_motion import temporarily_reduced_motion


def test_basic_fade_translate_midpoint():
    cfg = ScrollEffectConfig(fade_start=0.0, fade_end=0.5, min_opacity=0.2, translate_max=40)
    opacity, translate = compute_scroll_effect(50, 100, cfg, apply_perf_guard=False)
    assert 0.2 < opacity < 1.0
    assert translate < 0  # upward movement


def test_clamping_and_extremes():
    cfg = ScrollEffectConfig(fade_start=0.2, fade_end=0.4, min_opacity=0.3)
    # Before fade start
    o1, t1 = compute_scroll_effect(0, 100, cfg, apply_perf_guard=False)
    assert o1 == 1.0 and t1 == 0.0
    # After fade end
    o2, t2 = compute_scroll_effect(100, 100, cfg, apply_perf_guard=False)
    assert o2 == 0.3 and t2 == -cfg.translate_max


def test_reduced_motion_disables_effect():
    cfg = ScrollEffectConfig()
    with temporarily_reduced_motion(True):
        o, t = compute_scroll_effect(30, 100, cfg, apply_perf_guard=False)
        assert o == 1.0 and t == 0.0


def test_perf_guard_skips_after_threshold():
    cfg = ScrollEffectConfig(perf_calls_per_window=5, perf_window_ms=50)
    reset_scroll_effect_perf_counters()
    accepted = 0
    skipped = 0
    for _ in range(20):
        if should_apply_scroll_effect(cfg):
            accepted += 1
        else:
            skipped += 1
        # No sleep: all within same perf window
    assert accepted <= cfg.perf_calls_per_window
    assert skipped > 0
    # After window passes, counter resets
    time.sleep(cfg.perf_window_ms / 1000.0)
    assert should_apply_scroll_effect(cfg) is True


def test_invalid_config():
    try:
        ScrollEffectConfig(fade_start=0.6, fade_end=0.2).validate()
        assert False, "Expected fade range validation error"
    except ValueError:
        pass
