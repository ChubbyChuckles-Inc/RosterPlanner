"""Tests for maturity badge integration in the component gallery.

These tests exercise the pure helper functions without requiring PyQt6.
"""

from gui.components.gallery import (
    GalleryEntry,
    build_list_item_label,
    register_demo,
    clear_demos,
)
from gui.design.component_maturity import (
    ComponentMaturity,
    clear_component_maturity,
    register_component_maturity,
)


def setup_function(_):  # pytest style
    clear_demos()
    clear_component_maturity()


def test_build_list_item_label_with_maturity():
    # Register maturity
    register_component_maturity(
        ComponentMaturity(
            component_id="DemoWidget",
            status="alpha",
            description="Experimental widget",
        )
    )
    entry = GalleryEntry(name="DemoWidget", category="Test", factory=lambda: object())
    label = build_list_item_label(entry)
    assert label.endswith("[ALPHA]")


def test_build_list_item_label_without_maturity():
    entry = GalleryEntry(name="Untracked", category="Test", factory=lambda: object())
    label = build_list_item_label(entry)
    assert label == "Test / Untracked"  # no badge


def test_gallery_label_includes_stable_badge():
    register_component_maturity(
        ComponentMaturity(
            component_id="StableThing",
            status="stable",
            description="Done",
        )
    )
    entry = GalleryEntry(name="StableThing", category="Core", factory=lambda: object())
    label = build_list_item_label(entry)
    assert label.endswith("[STABLE]")
