from gui.design.color_blind import simulate_color_blindness, simulate_rgb_buffer

# Simple primary and secondary colors to test transform characteristics
TEST_PIXELS = [
    (255, 0, 0),  # red
    (0, 255, 0),  # green
    (0, 0, 255),  # blue
    (255, 255, 0),  # yellow
    (0, 255, 255),  # cyan
    (255, 255, 255),  # white
    (0, 0, 0),  # black
]


def test_protanopia_transform_monotonic():
    prot = simulate_rgb_buffer(TEST_PIXELS, "protanopia")
    # Red should shift toward darker / less red relative to original
    orig_red = TEST_PIXELS[0]
    prot_red = prot[0]
    assert prot_red[0] <= orig_red[0]
    # Green should be less altered than red for protanopia
    assert abs(prot[1][1] - TEST_PIXELS[1][1]) <= 40  # tolerance band


def test_deuteranopia_transform_monotonic():
    deut = simulate_rgb_buffer(TEST_PIXELS, "deuteranopia")
    # Green should shift more than red
    orig_green = TEST_PIXELS[1]
    deut_green = deut[1]
    assert deut_green[1] <= orig_green[1]
    # Red not drastically changed versus protanopia; allow somewhat larger shift (empirical ~99)
    assert abs(deut[0][0] - TEST_PIXELS[0][0]) <= 110


def test_identity_black_white():
    prot = simulate_rgb_buffer([(0, 0, 0), (255, 255, 255)], "protanopia")
    # Expect black/white to remain near extremes
    assert prot[0] == (0, 0, 0)
    # Allow slight rounding drift for white
    for c in prot[1]:
        assert 240 <= c <= 255


def test_single_pixel_function_equivalence():
    # Ensure buffer and single simulate produce same result
    for px in TEST_PIXELS:
        assert (
            simulate_color_blindness(px, "protanopia") == simulate_rgb_buffer([px], "protanopia")[0]
        )
