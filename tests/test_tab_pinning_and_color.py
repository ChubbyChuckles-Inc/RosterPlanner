from gui.views.document_area import DocumentArea
from gui.services.tab_metadata_persistence import TabMetadataPersistenceService


def test_tab_pinning_moves_left(qtbot, tmp_path):
    da = DocumentArea(base_dir=str(tmp_path))
    qtbot.addWidget(da)

    da.open_or_focus("a", "Alpha", lambda: object())
    da.open_or_focus("b", "Beta", lambda: object())
    da.open_or_focus("c", "Gamma", lambda: object())

    # Pin middle tab (b)
    da._tab_meta.set_pinned("b", True)
    da._reorder_pinned()

    # After reorder, Beta should be at index 0
    assert da.tabText(0).endswith("Beta") or "Beta" in da.tabText(0)

    # Pin c too; relative order of pinned b then c preserved
    da._tab_meta.set_pinned("c", True)
    da._reorder_pinned()
    titles = [da.tabText(i) for i in range(da.count())]
    # First two should contain Beta and Gamma (order of original indices among pinned)
    assert "Beta" in titles[0]
    assert "Gamma" in titles[1]


def test_tab_color_persistence(qtbot, tmp_path):
    base_dir = str(tmp_path)
    da = DocumentArea(base_dir=base_dir)
    qtbot.addWidget(da)
    da.open_or_focus("a", "Alpha", lambda: object())

    da._tab_meta.set_color("a", "#FF0000")
    da._apply_tab_metadata("a", 0)
    # Simulate recreation
    da2 = DocumentArea(base_dir=base_dir)
    qtbot.addWidget(da2)
    da2.open_or_focus("a", "Alpha", lambda: object())
    # Color should have been applied (cannot easily read QColor -> just ensure metadata present)
    assert da2._tab_meta.get("a").color == "#FF0000"
