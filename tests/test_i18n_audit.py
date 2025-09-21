from pathlib import Path

from gui.i18n import register_catalog, set_locale
import gui.i18n as i18n_mod
from gui.i18n.audit import collect_used_keys, audit_locales


def test_collect_used_keys_smoke(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text("from gui.i18n import t\nprint(t('alpha.key'))\n", encoding="utf-8")
    found = collect_used_keys([sample])
    assert "alpha.key" in found


def test_audit_locales_missing_and_unused(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    (code / "one.py").write_text(
        "from gui.i18n import t, tp\n" "t('present.key')\n" "tp('sing.one','sing.many',2)\n",
        encoding="utf-8",
    )
    # Snapshot and isolate catalogs to avoid interference from default entries.
    original_catalogs = dict(i18n_mod._catalogs)  # type: ignore[attr-defined]
    try:
        i18n_mod._catalogs.clear()  # type: ignore[attr-defined]
        # Register a locale with only some keys.
        register_catalog("en", {"present.key": "Present", "unused.key": "Unused"})
        register_catalog("fr", {"present.key": "Présent"})
        res = audit_locales([code])
        assert "en" in res and "fr" in res
        en_res = res["en"]
        fr_res = res["fr"]
        # Used keys: present.key, sing.one, sing.many
        assert en_res["missing"] == ["sing.many", "sing.one"]
        assert fr_res["missing"] == ["sing.many", "sing.one"]
        # Unused: unused.key should appear in en only
        assert en_res["unused"] == ["unused.key"]
        assert fr_res["unused"] == []
    finally:  # restore global state
        i18n_mod._catalogs.clear()  # type: ignore[attr-defined]
        i18n_mod._catalogs.update(original_catalogs)  # type: ignore[attr-defined]
