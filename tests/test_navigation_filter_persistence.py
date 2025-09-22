import json
import os
import tempfile

from gui.services.navigation_filter_persistence import (
    NavigationFilterPersistenceService,
    NavigationFilterState,
)


def test_navigation_filter_persistence_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        svc = NavigationFilterPersistenceService(base_dir=td)
        state = NavigationFilterState()
        state.search = "foo"
        state.division_types = {"Erwachsene"}
        state.levels = {"Stadtliga"}
        state.active_only = True
        assert svc.save(state)
        # Reload
        loaded = svc.load()
        assert loaded.search == "foo"
        assert loaded.division_types == {"Erwachsene"}
        assert loaded.levels == {"Stadtliga"}
        assert loaded.active_only is True


def test_navigation_filter_persistence_corrupt_file_backup():
    with tempfile.TemporaryDirectory() as td:
        svc = NavigationFilterPersistenceService(base_dir=td)
        path = os.path.join(td, "navigation_filters.json")
        # Write corrupt content
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ not valid json")
        loaded = svc.load()
        # Should return default state and rename corrupt file
        assert loaded.search == ""
        backups = [p for p in os.listdir(td) if p.startswith("navigation_filters.json.corrupt")]
        assert backups, "Expected corrupt backup file"
