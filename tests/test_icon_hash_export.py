from pathlib import Path
import json
import time

from gui.design.icons import (
    register_icon,
    clear_icons,
    export_icon_hash_map,
    compute_icon_hash,
)


def test_export_icon_hash_map_creates_file(tmp_path):
    svg = tmp_path / "alpha.svg"
    svg.write_text("<svg><circle/></svg>", encoding="utf-8")
    clear_icons()
    register_icon("alpha-icon", svg)
    out = tmp_path / "icon-hashes.json"
    data = export_icon_hash_map(out)
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == data
    assert "alpha-icon" in data
    assert data["alpha-icon"]["hash"] == compute_icon_hash("alpha-icon")


def test_export_icon_hash_map_updates_after_change(tmp_path):
    svg = tmp_path / "beta.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    clear_icons()
    register_icon("beta-icon", svg)
    out = tmp_path / "icon-hashes.json"
    first = export_icon_hash_map(out)
    h1 = first["beta-icon"]["hash"]
    time.sleep(0.001)
    svg.write_text("<svg><rect/></svg>", encoding="utf-8")
    second = export_icon_hash_map(out)
    h2 = second["beta-icon"]["hash"]
    assert h1 != h2
