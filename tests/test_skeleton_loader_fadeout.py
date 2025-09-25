from gui.components.skeleton_loader import SkeletonLoaderWidget

def test_skeleton_loader_fadeout(qtbot):
    w = SkeletonLoaderWidget("table-row", rows=1, shimmer=False)
    qtbot.addWidget(w)
    w.start()
    assert w.is_active()
    w.stop()
    # After calling stop() it should mark inactive immediately
    assert not w.is_active()
    # We can't rely on animation completion in test environment; ensure widget scheduled to hide
    # If reduced motion is enabled it will already be hidden.
    # Use a short wait loop.
    qtbot.wait(250)
    assert not w.isVisible()
