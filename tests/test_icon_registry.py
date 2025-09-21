from pathlib import Path
import pytest
from gui.design import register_icon, get_icon_path, list_icons, clear_icons

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons" / "base"


def setup_function(_func):
    clear_icons()
    # re-register placeholder each test
    placeholder = ASSETS_DIR / "placeholder.svg"
    if placeholder.exists():
        register_icon("placeholder", placeholder)


def test_placeholder_registered():
    path = get_icon_path("placeholder")
    assert path.name == "placeholder.svg"


def test_register_and_retrieve_new_icon(tmp_path):
    # create temp svg
    svg = tmp_path / "custom.svg"
    svg.write_text(
        '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    register_icon("custom", svg)
    assert get_icon_path("custom") == svg


def test_duplicate_registration_errors(tmp_path):
    svg = tmp_path / "dup.svg"
    svg.write_text(
        '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    register_icon("dup", svg)
    with pytest.raises(KeyError):
        register_icon("dup", svg)


def test_override_allows_replacement(tmp_path):
    svg1 = tmp_path / "one.svg"
    svg1.write_text(
        '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    register_icon("swap", svg1)
    svg2 = tmp_path / "two.svg"
    svg2.write_text(
        '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    from gui.design.icons import register_icon as reg  # access override argument

    reg("swap", svg2, override=True)
    assert get_icon_path("swap") == svg2


def test_missing_icon_errors():
    with pytest.raises(KeyError):
        get_icon_path("does-not-exist")


def test_invalid_name_rejected(tmp_path):
    svg = tmp_path / "bad.svg"
    svg.write_text(
        '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    with pytest.raises(ValueError):
        register_icon("BadCase", svg)


def test_list_icons_returns_descriptors():
    names = {d.name for d in list_icons()}
    assert "placeholder" in names
