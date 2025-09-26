import json
from pathlib import Path
from gui.services.export_service import ExportService, ExportFormat
from gui.services.export_presets import ExportPresetsService, DERIVED_PLACEHOLDER
from gui.services.service_locator import services
import types


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


def test_derived_placeholder_expands(tmp_path: Path):
    """Preset containing *derived expands to current derived field names.

    We simulate a rule_version_store service exposing latest() -> object
    with rules_json containing a 'derived' mapping.
    """
    # Fake rule version entry
    entry = types.SimpleNamespace(
        rules_json='{"derived": {"FormScore": "expr1", "AggRating": "expr2"}}'
    )
    store = types.SimpleNamespace(latest=lambda: entry)
    services.register("rule_version_store", store, allow_override=True)

    presets = ExportPresetsService(base_dir=str(tmp_path))
    presets.add_or_replace("with_derived", ["Player", DERIVED_PLACEHOLDER])
    export_svc = ExportService()

    # Dummy includes derived columns so expansion is meaningful
    class DummyWithDerived:
        def get_export_rows(self):  # pragma: no cover - simple
            return [
                "Player",
                "FormScore",
                "AggRating",
                "LivePZ",
            ], [["A", "1", "200", "1200"], ["B", "2", "180", "1100"]]

    dummy = DummyWithDerived()
    result = presets.apply(export_svc, dummy, ExportFormat.CSV, "with_derived")
    first_line = result.content.splitlines()[0]
    # Expect Player followed by derived fields (order preserved)
    assert first_line in ("Player,FormScore,AggRating", "Player,AggRating,FormScore")
    # Cleanup service locator side-effect
    services.unregister("rule_version_store")
