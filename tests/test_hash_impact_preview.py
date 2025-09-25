import os
import sqlite3
import hashlib
import time
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


def _write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_hash_impact_preview_new_updated_missing(tmp_path):
    from gui.views.ingestion_lab_panel import IngestionLabPanel
    from gui.services.service_locator import services

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create three files: a.html, b.html, c.html
    a_path = data_dir / "ranking_table_a.html"
    b_path = data_dir / "ranking_table_b.html"
    c_path = data_dir / "ranking_table_c.html"
    _write_file(a_path, "<html>a1</html>")
    _write_file(b_path, "<html>b1</html>")
    _write_file(c_path, "<html>c1</html>")

    # Prepare provenance with a.html (old hash), b.html (current hash), and ghost.html (missing)
    old_a_hash = hashlib.sha1(b"<html>a0</html>").hexdigest()  # different from current a1
    cur_b_hash = hashlib.sha1(b"<html>b1</html>").hexdigest()

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT, last_ingested_at TEXT, parser_version INTEGER)"
    )
    conn.execute(
        "INSERT INTO provenance(path, sha1, last_ingested_at, parser_version) VALUES(?,?,datetime('now'),1)",
        (str(a_path), old_a_hash),
    )
    conn.execute(
        "INSERT INTO provenance(path, sha1, last_ingested_at, parser_version) VALUES(?,?,datetime('now'),1)",
        (str(b_path), cur_b_hash),
    )
    # Missing file entry
    missing_path = data_dir / "ranking_table_missing.html"
    conn.execute(
        "INSERT INTO provenance(path, sha1, last_ingested_at, parser_version) VALUES(?,?,datetime('now'),1)",
        (str(missing_path), "deadbeef"),
    )

    with services.override_context(sqlite_conn=conn):
        panel = IngestionLabPanel(base_dir=str(data_dir))
        panel.refresh_file_list()
        res = panel.compute_hash_impact()

    # Assertions
    # a should be in updated, b unchanged, c new, missing_path in missing
    assert any(str(a_path) == p for p in res.updated)
    assert any(str(b_path) == p for p in res.unchanged)
    assert any(str(c_path) == p for p in res.new)
    assert any(str(missing_path) == p for p in res.missing)
    # No overlap between categories
    sets = [set(res.updated), set(res.unchanged), set(res.new), set(res.missing)]
    all_union = set().union(*sets)
    assert sum(len(s) for s in sets) == len(all_union)


def test_hash_impact_button_logs(tmp_path, qtbot):
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sample = data_dir / "team_roster_alpha.html"
    _write_file(sample, "<html>x</html>")

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()
    panel.btn_hash_impact.click()
    text = panel.log_area.toPlainText()
    assert "Hash Impact:" in text
