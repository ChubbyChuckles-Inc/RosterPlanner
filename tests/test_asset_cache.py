import tempfile
from pathlib import Path
from gui.design.asset_cache import (
    register_asset,
    get_asset,
    list_assets,
    clear_assets,
    save_manifest,
    load_manifest,
    compute_file_hash,
)
import json
import pytest


def setup_function():
    clear_assets()


def _write_file(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


def test_register_and_retrieve():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        f = _write_file(tmp, "icon1.svg", "<svg></svg>")
        entry = register_asset(f)
        fetched = get_asset(entry.id)
        assert fetched.sha256 == entry.sha256
        assert fetched.version == 1
        assert len(list(list_assets())) == 1


def test_re_register_changes_version_on_content_update():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        f = _write_file(tmp, "icon2.svg", "<svg>a</svg>")
        e1 = register_asset(f)
        # modify file
        f.write_text("<svg>b</svg>", encoding="utf-8")
        e2 = register_asset(f)
        assert e2.version == e1.version + 1
        assert e2.sha256 != e1.sha256


def test_manifest_round_trip():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        f = _write_file(tmp, "font.woff", "binarydata")
        register_asset(f, type="font")
        manifest_path = tmp / "cache.json"
        save_manifest(manifest_path)
        clear_assets()
        loaded_count = load_manifest(manifest_path)
        assert loaded_count == 1
        assert len(list(list_assets())) == 1


def test_compute_file_hash_changes():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        f = _write_file(tmp, "file.txt", "one")
        h1 = compute_file_hash(f)
        f.write_text("two", encoding="utf-8")
        h2 = compute_file_hash(f)
        assert h1 != h2


def test_invalid_type():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        f = _write_file(tmp, "file.bin", "data")
        with pytest.raises(ValueError):
            register_asset(f, type="audio")


def test_missing_file_hash():
    with pytest.raises(FileNotFoundError):
        compute_file_hash("does_not_exist.xyz")
