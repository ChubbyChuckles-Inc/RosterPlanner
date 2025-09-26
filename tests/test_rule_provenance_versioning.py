import sqlite3, json
from PyQt6.QtWidgets import QApplication
from gui.views.ingestion_lab_panel import IngestionLabPanel
from gui.services.service_locator import services

app = QApplication.instance() or QApplication([])

RULES = {"version":1, "resources": {"players": {"kind":"list","selector":"ul.p","item_selector":"li","fields":{"name":{"selector":"span.n"}}}}}
HTML = """<html><body><ul class='p'><li><span class='n'>A</span></li></ul></body></html>"""

def test_provenance_rule_version_written(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    f = data_dir / 'team_roster_test.html'
    f.write_text(HTML, encoding='utf-8')
    conn = sqlite3.connect(':memory:')
    services.register('sqlite_conn', conn, allow_override=True)
    panel = IngestionLabPanel(base_dir=str(data_dir))
    panel.rule_editor.setPlainText(json.dumps(RULES))
    panel._on_simulate_clicked()
    panel._on_apply_clicked()
    cur = conn.execute("SELECT rule_version FROM provenance WHERE path=?", (str(f),))
    row = cur.fetchone()
    assert row is not None and row[0] == 1
