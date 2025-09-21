from gui.design.loader import load_tokens
from gui.design.density_manager import DensityManager


def test_density_default_mode():
    tokens = load_tokens()
    dm = DensityManager(tokens)
    spacing = dm.active_spacing()
    # Expect some known spacing keys to remain identical in comfortable mode
    if "md" in spacing and isinstance(tokens.raw["spacing"].get("md"), int):
        assert spacing["md"] == tokens.raw["spacing"]["md"]


def test_density_compact_mode_scaling():
    tokens = load_tokens()
    dm = DensityManager(tokens)
    base_spacing = dm.active_spacing().copy()
    diff = dm.set_mode("compact")
    assert not diff.no_changes
    compact_spacing = dm.active_spacing()
    # Pick a key that exists
    key = next(iter(base_spacing))
    assert compact_spacing[key] <= base_spacing[key]
    # zero stays zero, positive not below 1
    if 0 in base_spacing.values():
        for k, v in base_spacing.items():
            if v == 0:
                assert compact_spacing[k] == 0
    for k, v in base_spacing.items():
        if v > 0:
            assert compact_spacing[k] >= 1


def test_density_idempotent_switch():
    tokens = load_tokens()
    dm = DensityManager(tokens)
    dm.set_mode("compact")
    first = dm.active_spacing().copy()
    diff = dm.set_mode("compact")
    assert diff.no_changes
    assert first == dm.active_spacing()


def test_scale_value_helper():
    tokens = load_tokens()
    dm = DensityManager(tokens)
    assert dm.scale_value(0) == 0
    assert dm.scale_value(10) == 10
    dm.set_mode("compact")
    assert dm.scale_value(10) <= 10
    assert dm.scale_value(1) >= 1  # safeguard against 0
