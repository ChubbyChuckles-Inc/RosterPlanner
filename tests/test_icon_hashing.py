from pathlib import Path
import time

import pytest

from gui.design.icons import (
    register_icon,
    get_icon_path,
    clear_icons,
    compute_icon_hash,
    get_icon_hash_map,
)


@pytest.fixture()
def temp_icon(tmp_path):
    svg = tmp_path / "sample.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    clear_icons()
    register_icon("sample-icon", svg)
    return svg


def test_compute_icon_hash_stable(temp_icon):
    h1 = compute_icon_hash("sample-icon")
    h2 = compute_icon_hash("sample-icon")
    assert h1 == h2  # cached


def test_compute_icon_hash_changes_on_modify(temp_icon):
    h1 = compute_icon_hash("sample-icon")
    time.sleep(0.001)  # ensure mtime precision difference
    temp_icon.write_text("<svg><rect/></svg>", encoding="utf-8")
    h2 = compute_icon_hash("sample-icon")
    assert h1 != h2


def test_get_icon_hash_map_contains_entry(temp_icon):
    mapping = get_icon_hash_map()
    assert "sample-icon" in mapping
    assert len(mapping["sample-icon"]) == 10
