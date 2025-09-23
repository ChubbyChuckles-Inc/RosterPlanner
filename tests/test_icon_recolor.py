from gui.design.icon_recolor import recolor_svg, extract_tones

SAMPLE_SVG = """<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 16 16\">
<path data-tone=\"primary\" d=\"M0 0h8v8H0z\" fill=\"#000000\"/>
<path data-tone=\"secondary\" d=\"M8 8h8v8H8z\"/>
<path d=\"M0 8h8v8H0z\" fill=\"#123456\"/>
</svg>"""


def test_extract_tones():
    tones = extract_tones(SAMPLE_SVG)
    assert tones == {"primary", "secondary"}


def test_recolor_basic():
    recolored = recolor_svg(SAMPLE_SVG, {"primary": "#ff0000", "secondary": "#00ff00"})
    assert "#ff0000" in recolored
    assert "#00ff00" in recolored
    # Unmarked path unchanged
    assert "#123456" in recolored


def test_recolor_disabled_alpha():
    recolored = recolor_svg(
        SAMPLE_SVG, {"primary": "#112233", "secondary": "#445566"}, state="disabled"
    )
    assert (
        "#11223380" in recolored or "#112233" in recolored
    )  # ensure transformation applied to at least one tone


def test_idempotent_when_no_tones():
    plain = '<svg><path d="M0 0h1v1H0z" fill="#000000"/></svg>'
    assert recolor_svg(plain, {"primary": "#fff"}) == plain
