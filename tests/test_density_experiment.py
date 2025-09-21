from gui.design.density_experiment import (
    list_density_variants,
    current_density_variant,
    set_density_variant,
    density_history,
    register_density_listener,
    clear_density_state,
)


def setup_function():
    clear_density_state()


def test_variants_list_contains_expected():
    variants = list_density_variants()
    assert "comfortable" in variants and "compact" in variants


def test_switch_and_history():
    assert current_density_variant() == "comfortable"
    set_density_variant("compact")
    set_density_variant("cozy")
    hist = density_history()
    # initial + 2 switches
    assert len(hist) == 3
    assert hist[-1].variant == "cozy"


def test_idempotent_switch():
    before = density_history()
    set_density_variant("comfortable")  # same as default -> suppressed
    after = density_history()
    assert len(after) == len(before)  # no new entry


def test_listener_notified():
    received = []

    def listener(state):
        received.append(state.variant)

    register_density_listener(listener)
    set_density_variant("compact")
    assert received[-1] == "compact"


def test_history_trim():
    # push more than max history (50); start from default already present
    for i in range(60):
        set_density_variant("compact" if i % 2 == 0 else "cozy")
    hist = density_history()
    assert len(hist) <= 50
