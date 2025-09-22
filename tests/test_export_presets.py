import json
from pathlib import Path
from gui.services.export_service import ExportService, ExportFormat
from gui.services.export_presets import ExportPresetsService


class DummyTabular:
    def get_export_rows(self):  # pragma: no cover - simple
        return ["Player", "LivePZ", "Trend"], [["A", "1200", "++++"], ["B", "1100", "--"]]


def test_presets_round_trip(tmp_path: Path):
    svc = ExportPresetsService(base_dir=str(tmp_path))
    svc.add_or_replace("minimal", ["Player", "LivePZ"])
    # Reload new instance to verify persistence
    svc2 = ExportPresetsService(base_dir=str(tmp_path))
    svc2.load()
    p = svc2.get("minimal")
    assert p is not None
    assert p.columns == ["Player", "LivePZ"]


def test_apply_preset_filters_columns(tmp_path: Path):
    presets = ExportPresetsService(base_dir=str(tmp_path))
    presets.add_or_replace("trend_only", ["Player", "Trend"])
    export_svc = ExportService()
    dummy = DummyTabular()
    result = presets.apply(export_svc, dummy, ExportFormat.CSV, "trend_only")
    lines = result.content.strip().splitlines()
    assert lines[0] == "Player,Trend"
    # Ensure LivePZ removed
    assert "LivePZ" not in result.content


def test_apply_missing_preset_falls_back(tmp_path: Path):
    presets = ExportPresetsService(base_dir=str(tmp_path))
    export_svc = ExportService()
    dummy = DummyTabular()
    result = presets.apply(export_svc, dummy, ExportFormat.JSON, "does_not_exist")
    # Should include all three fields
    assert "LivePZ" in result.content and "Trend" in result.content
