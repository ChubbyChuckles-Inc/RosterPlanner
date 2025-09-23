from gui.design.color_vision_simulation import simulate_hex, transform_palette


def test_simulate_hex_passthrough_invalid_mode():
    assert simulate_hex("#112233", None) == "#112233"
    assert simulate_hex("#112233", "unknown") == "#112233"


def test_transform_palette_changes_some_values():
    palette = {"accent.base": "#FF0000", "text.primary": "#00FF00", "misc": "not-a-color"}
    prot = transform_palette(palette, "protanopia")
    deut = transform_palette(palette, "deuteranopia")
    # Some keys should change while non-hex stays same
    assert prot["misc"] == "not-a-color"
    assert deut["misc"] == "not-a-color"
    assert (
        prot["accent.base"] != palette["accent.base"]
        or prot["text.primary"] != palette["text.primary"]
    )
    assert (
        deut["accent.base"] != palette["accent.base"]
        or deut["text.primary"] != palette["text.primary"]
    )
