from gui.services.export_service import ExportService, ExportFormat


class DummyTabular:
    def get_export_rows(self):  # pragma: no cover - simple
        return ["A", "B"], [["1", "2"], ["3", "4"]]


class DummyJson:
    def get_export_payload(self):  # pragma: no cover - simple
        return {"k": 1, "arr": [1, 2, 3]}


def test_export_csv_basic():
    svc = ExportService()
    dummy = DummyTabular()
    result = svc.export(dummy, ExportFormat.CSV)
    assert result.format == ExportFormat.CSV
    assert result.suggested_extension == ".csv"
    # Header plus two rows
    lines = [l for l in result.content.strip().splitlines() if l]
    assert lines[0] == "A,B"
    assert "1,2" in lines[1]
    assert "3,4" in lines[2]


def test_export_json_prefers_payload():
    svc = ExportService()
    dummy = DummyJson()
    result = svc.export(dummy, ExportFormat.JSON)
    assert result.format == ExportFormat.JSON
    assert '"k": 1' in result.content
    assert result.content.strip().startswith("{")
    assert result.content.strip().endswith("}")


def test_export_json_fallback_to_tabular():
    svc = ExportService()
    dummy = DummyTabular()
    result = svc.export(dummy, ExportFormat.JSON)
    assert result.format == ExportFormat.JSON
    # Should produce list of objects
    assert result.content.strip().startswith("[")
    assert '"A"' in result.content
    assert '"B"' in result.content
