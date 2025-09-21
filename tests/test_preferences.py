"""Tests for user preferences persistence (Milestone 0.26)."""

from gui.app.preferences import (
    UserPreferences,
    load_preferences,
    save_preferences,
    PREF_VERSION,
)
import json


def test_round_trip_preferences(tmp_path):
    prefs = UserPreferences(
        theme="dark", accent="#FF0000", density="compact", high_contrast=True, reduce_motion=True
    )
    save_preferences(prefs, tmp_path)
    loaded = load_preferences(tmp_path)
    assert loaded == prefs


def test_corrupt_file_fallback(tmp_path):
    path = tmp_path / "user_prefs.json"
    path.write_text("not valid json", encoding="utf-8")
    loaded = load_preferences(tmp_path)
    assert isinstance(loaded, UserPreferences)
    assert loaded.version == PREF_VERSION


def test_version_mismatch_resets(tmp_path, monkeypatch):
    prefs = UserPreferences(theme="light")
    save_preferences(prefs, tmp_path)
    # simulate future version bump
    data = json.loads((tmp_path / "user_prefs.json").read_text(encoding="utf-8"))
    data["version"] = 999
    (tmp_path / "user_prefs.json").write_text(json.dumps(data), encoding="utf-8")
    loaded = load_preferences(tmp_path)
    assert loaded.version == PREF_VERSION
    # theme preserved
    assert loaded.theme == "light"
