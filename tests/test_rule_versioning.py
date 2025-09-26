import sqlite3
import json
from gui.ingestion.rule_versioning import RuleSetVersionStore


def test_version_store_basic_insert_and_skip_duplicate():
    conn = sqlite3.connect(":memory:")
    store = RuleSetVersionStore(conn)
    payload_v1 = {"version": 1, "resources": {"x": 1}}
    v1 = store.save_version(payload_v1, json.dumps(payload_v1))
    assert v1 == 1
    # Duplicate hash should return existing version number
    v1_again = store.save_version(payload_v1, json.dumps(payload_v1))
    assert v1_again == 1
    # Change payload -> new version
    payload_v2 = {"version": 1, "resources": {"x": 2}}
    v2 = store.save_version(payload_v2, json.dumps(payload_v2))
    assert v2 == 2
    versions = store.list_versions()
    assert [v.version_num for v in versions] == [2, 1]
    prev_json = store.rollback_to_previous()
    # Latest is v2 -> previous returns v1 JSON
    assert '"x": 1' in prev_json
