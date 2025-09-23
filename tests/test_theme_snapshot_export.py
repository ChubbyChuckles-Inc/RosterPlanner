import json
import os
import time
from pathlib import Path

from gui.services.theme_service import ThemeService, export_theme_snapshot
from gui.services.service_locator import services


def setup_module(module):  # noqa: D401 - test setup
    # Ensure a ThemeService is registered for the export helper
    services.register("theme_service", ThemeService.create_default(), allow_override=True)


def teardown_module(module):  # noqa: D401 - test teardown
    services._services.pop("theme_service", None)  # type: ignore[attr-defined]


def test_snapshot_structure():
    svc: ThemeService = services.get_typed("theme_service", ThemeService)
    snap = svc.snapshot()
    assert isinstance(snap, dict)
    assert snap["variant"] == svc.manager.variant
    assert snap["accent_base"].startswith("#")
    assert snap["color_count"] == len(svc.colors())
    assert isinstance(snap["colors"], list) and snap["colors"], "Expected non-empty colors list"
    # Ensure ordering is sorted by key
    keys = [c["key"] for c in snap["colors"]]
    assert keys == sorted(keys)
    assert all("value" in c for c in snap["colors"])
    assert "metadata" in snap and "exported_at" in snap["metadata"]
    assert snap["missing_required"] == [], f"Required keys missing: {snap['missing_required']}"


def test_export_to_file(tmp_path):
    out_file = tmp_path / "theme_snapshot.json"
    path_written = export_theme_snapshot(str(out_file))
    assert path_written == str(out_file)
    assert out_file.exists()
    data = json.loads(out_file.read_text("utf-8"))
    assert data["color_count"] >= 1
    assert any(c["key"] == "background.primary" for c in data["colors"])  # sanity
    # timestamp sanity (within 5s)
    assert abs(time.time() - data["metadata"]["exported_at"]) < 5
