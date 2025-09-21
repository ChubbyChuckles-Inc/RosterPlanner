from gui.app.config_store import (
    AppConfig,
    load_config,
    save_config,
    CONFIG_VERSION,
    WINDOW_STATE_VERSION,
)
from pathlib import Path
import json


def test_load_returns_defaults_when_missing(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg.version == CONFIG_VERSION
    assert cfg.last_data_dir is None
    assert cfg.window_x is None


def test_save_and_reload_round_trip(tmp_path: Path):
    cfg = AppConfig(window_x=10, window_y=20, window_w=800, window_h=600, last_data_dir="data")
    save_config(cfg, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded.to_dict() == cfg.to_dict()


def test_corrupt_file_graceful_fallback(tmp_path: Path):
    p = tmp_path / "app_state.json"
    p.write_text("not json", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert isinstance(cfg, AppConfig)
    assert cfg.window_x is None


def test_version_mismatch_resets_but_preserves_last_dir(tmp_path: Path):
    # Write a config with a different version
    p = tmp_path / "app_state.json"
    data = {
        "version": CONFIG_VERSION + 10,
        "window_x": 1,
        "window_y": 2,
        "window_w": 3,
        "window_h": 4,
        "maximized": True,
        "last_data_dir": "keepme",
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.window_x is None  # reset
    assert cfg.last_data_dir == "keepme"  # preserved


def test_window_state_version_mismatch_clears_geometry(tmp_path: Path):
    # Create a valid config then manually alter window_state_version
    cfg = AppConfig(
        window_x=10,
        window_y=20,
        window_w=800,
        window_h=600,
        maximized=True,
        last_data_dir="d",
    )
    save_config(cfg, tmp_path)
    p = tmp_path / "app_state.json"
    data = p.read_text(encoding="utf-8")
    import json as _json

    obj = _json.loads(data)
    obj["window_state_version"] = WINDOW_STATE_VERSION + 5
    p.write_text(_json.dumps(obj), encoding="utf-8")
    reloaded = load_config(tmp_path)
    assert reloaded.window_x is None
    assert reloaded.maximized is False
    assert reloaded.window_state_version == WINDOW_STATE_VERSION
