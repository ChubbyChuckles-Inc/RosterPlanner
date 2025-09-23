from gui.design.contrast_heatmap import (
    ContrastSampleInput,
    analyze_contrast,
)


def test_contrast_heatmap_basic_pass_and_fail():
    samples = [
        ContrastSampleInput(id="ok1", fg="#FFFFFF", bg="#000000"),
        ContrastSampleInput(id="fail1", fg="#777777", bg="#6F6F6F"),
        ContrastSampleInput(id="large_ok", fg="#666666", bg="#FFFFFF", meta={"large_text": True}),
    ]
    report = analyze_contrast(samples)
    ids = {i.id: i for i in report.issues}
    assert ids["ok1"].level == "pass"
    assert ids["fail1"].level == "fail"
    assert ids["large_ok"].required == 3.0  # large text threshold applied
    assert report.summary["total"] == 3
    assert report.summary["failing"] >= 1
