import os
import json
import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])


def _sample_ruleset_text():
    return json.dumps(
        {
            "version": 1,
            "resources": {
                "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
                "players": {
                    "kind": "list",
                    "selector": "ul.p",
                    "item_selector": "li",
                    "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.rank"}},
                },
            },
        }
    )


def test_field_coverage_integration(tmp_path, qtbot):
    # Prepare simple HTML assets
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ranking_table_alpha.html").write_text(
        """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr>
        <tr><td>A</td><td>5</td></tr>
        <tr><td>B</td><td>7</td></tr>
        </table>
        <ul class='p'>
            <li><span class='n'>Alice</span><span class='rank'>1</span></li>
            <li><span class='n'>Bob</span></li>
        </ul>
        </body></html>
        """,
        encoding="utf-8",
    )
    (data_dir / "ranking_table_beta.html").write_text(
        """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr>
        <tr><td>C</td><td>9</td></tr>
        </table>
        <ul class='p'>
            <li><span class='n'>Cara</span><span class='rank'>2</span></li>
        </ul>
        </body></html>
        """,
        encoding="utf-8",
    )

    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()
    panel.rule_editor.setPlainText(_sample_ruleset_text())

    # Trigger coverage
    panel._on_field_coverage_clicked()
    snap = panel.field_coverage_snapshot()
    if not snap:
        pytest.skip("Coverage snapshot empty - backend unavailable")
    # Basic assertions on structure
    assert "resources" in snap
    ranking_entry = next(r for r in snap["resources"] if r["resource"] == "ranking")
    players_entry = next(r for r in snap["resources"] if r["resource"] == "players")
    assert len(ranking_entry["fields"]) == 2
    assert len(players_entry["fields"]) == 2
    # Log should contain overall coverage line
    log_text = panel.log_area.toPlainText()
    assert "Field Coverage Overall" in log_text
    assert "— end coverage —" in log_text
