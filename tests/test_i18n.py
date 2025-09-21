from gui.i18n import (
    register_catalog,
    set_locale,
    get_locale,
    t,
    tp,
    extract_translation_keys,
)


def test_basic_translation_and_fallback():
    set_locale("en")
    assert t("greeting.hello") == "Hello from project-template!"
    # Register a second locale with a subset of keys.
    register_catalog("de", {"greeting.hello": "Hallo vom Projekt-Template!"})
    set_locale("de")
    assert t("greeting.hello").startswith("Hallo")
    # Missing in de, fallback to en
    assert t("greeting.named", name="Ada") == "Hello Ada"


def test_pluralisation_basic():
    set_locale("en")
    one = tp("items.count.one", "items.count.other", 1)
    many = tp("items.count.one", "items.count.other", 5)
    assert one == "1 item"
    assert many == "5 items"


def test_interpolation_missing_variable_raises():
    set_locale("en")
    try:
        t("greeting.named")  # missing name
    except KeyError as e:
        assert "Missing interpolation variable" in str(e)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected KeyError for missing interpolation variable")


def test_extract_translation_keys(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        """from gui.i18n import t, tp\n"""
        "print(t('alpha.bravo'))\n"
        "print(tp('sing.one','sing.many', 2))\n",
        encoding="utf-8",
    )
    found = extract_translation_keys([sample])
    assert {"alpha.bravo", "sing.one", "sing.many"}.issubset(found)
