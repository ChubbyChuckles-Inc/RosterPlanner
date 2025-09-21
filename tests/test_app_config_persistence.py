from gui.app.config_store import load_config, save_config, AppConfig
from gui.app.config_helpers import update_last_data_dir, record_window_geometry
from pathlib import Path
import json


def test_config_defaults(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert isinstance(cfg, AppConfig)
    assert cfg.last_data_dir is None
    assert cfg.data_dir_history is None


def test_config_save_and_reload(tmp_path: Path):
    cfg = load_config(tmp_path)
    update_last_data_dir(cfg, str(tmp_path / "data1"))
    record_window_geometry(cfg, x=10, y=20, w=800, h=600, maximized=False, raw="raw_blob")
    save_config(cfg, tmp_path)

    reloaded = load_config(tmp_path)
    assert reloaded.last_data_dir.endswith("data1")
    assert reloaded.window_x == 10 and reloaded.window_w == 800
    assert reloaded.window_geometry_raw == "raw_blob"
    assert reloaded.data_dir_history and reloaded.data_dir_history[0].endswith("data1")


def test_update_last_data_dir_history(tmp_path: Path):
    cfg = AppConfig()
    update_last_data_dir(cfg, "A")
    update_last_data_dir(cfg, "B")
    update_last_data_dir(cfg, "A")  # Move A to front again
    assert cfg.data_dir_history == ["A", "B"]

    # Add many to trigger cap
    for i in range(20):
        update_last_data_dir(cfg, f"dir{i}")
    assert len(cfg.data_dir_history) == 10
