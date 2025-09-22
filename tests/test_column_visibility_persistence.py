from gui.services.column_visibility_persistence import (
    ColumnVisibilityPersistenceService,
    ColumnVisibilityState,
)


def test_column_visibility_save_load(tmp_path):
    svc = ColumnVisibilityPersistenceService(str(tmp_path))
    st = svc.load()
    assert st.visible == {}
    st.set_visible("player", False)
    st.set_visible("live_pz", True)
    svc.save(st)

    st2 = svc.load()
    assert st2.is_visible("player") is False
    assert st2.is_visible("live_pz") is True
    # Unknown defaults to True
    assert st2.is_visible("unknown") is True
