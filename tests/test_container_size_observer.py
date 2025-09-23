from gui.services.container_size_observer import evaluate_profile


def test_evaluate_profile_boundaries():
    # Negative coerced to 0 -> narrow
    p0 = evaluate_profile(-10)
    assert p0.profile == "narrow"
    assert p0.density == "compact"
    assert 0.9 < p0.type_scale < 0.93

    p1 = evaluate_profile(0)
    assert p1.profile == "narrow"

    p2 = evaluate_profile(799)
    assert p2.profile == "narrow"

    p3 = evaluate_profile(800)
    assert p3.profile == "medium"
    assert p3.density == "comfortable"
    assert p3.type_scale == 1.0

    p4 = evaluate_profile(1199)
    assert p4.profile == "medium"

    p5 = evaluate_profile(1200)
    assert p5.profile == "wide"
    assert p5.type_scale > 1.0


def test_evaluate_profile_monotonic():
    # Ensure widths produce non-decreasing ordering narrow -> medium -> wide
    seq = [100, 900, 1500]
    labels = [evaluate_profile(w).profile for w in seq]
    assert labels == ["narrow", "medium", "wide"]
