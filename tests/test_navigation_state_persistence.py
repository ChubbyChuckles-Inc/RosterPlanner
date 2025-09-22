import os
import tempfile
from gui.services.navigation_state_persistence import (
    NavigationStatePersistenceService,
    NavigationState,
)


def test_navigation_state_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        svc = NavigationStatePersistenceService(td)
        st = NavigationState()
        st.expanded_divisions = {"DivA", "DivB"}
        st.last_selected_team_id = "team123"
        assert svc.save(st)
        loaded = svc.load()
        assert loaded.expanded_divisions == {"DivA", "DivB"}
        assert loaded.last_selected_team_id == "team123"


def test_navigation_state_corrupt_backup():
    with tempfile.TemporaryDirectory() as td:
        svc = NavigationStatePersistenceService(td)
        path = os.path.join(td, "navigation_state.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ not valid json")
        loaded = svc.load()
        assert loaded.expanded_divisions == set()
        backups = [p for p in os.listdir(td) if p.startswith("navigation_state.json.corrupt")]
        assert backups, "Expected corrupt backup file"
