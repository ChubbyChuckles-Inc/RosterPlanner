from gui.components.gallery import (
    register_demo,
    list_demos,
    get_demo,
    clear_demos,
)


def setup_function(_fn):
    clear_demos()


def test_register_and_list_demo():
    register_demo("button-basic", "Buttons", lambda: object(), description="Basic button")
    demos = list_demos()
    assert len(demos) == 1
    entry = demos[0]
    assert entry.name == "button-basic"
    assert entry.category == "Buttons"
    assert entry.description == "Basic button"


def test_hidden_flag_excludes_from_default_list():
    register_demo("secret", "Misc", lambda: object(), hidden=True)
    assert len(list_demos()) == 0
    assert len(list_demos(include_hidden=True)) == 1


def test_get_demo():
    register_demo("table", "Data", lambda: {"demo": True})
    entry = get_demo("table")
    assert entry.create()["demo"] is True


def test_duplicate_registration_errors():
    register_demo("dup", "Misc", lambda: None)
    try:
        register_demo("dup", "Misc", lambda: None)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError for duplicate demo registration")
