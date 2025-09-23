from gui.services.focus_trail_service import FocusTrailService


class Dummy:
    pass


def test_focus_trail_basic_order_and_capacity():
    svc = FocusTrailService(capacity=3)
    a, b, c, d = Dummy(), Dummy(), Dummy(), Dummy()
    svc.add_focus_object(a)
    svc.add_focus_object(b)
    svc.add_focus_object(c)
    assert svc.trail_ids() == [id(c), id(b), id(a)]
    # Add existing again should move to front without duplicating
    svc.add_focus_object(b)
    assert svc.trail_ids() == [id(b), id(c), id(a)]
    # Adding new beyond capacity evicts oldest
    svc.add_focus_object(d)
    assert svc.trail_ids() == [id(d), id(b), id(c)]


def test_focus_trail_clear():
    svc = FocusTrailService(capacity=2)
    x, y = Dummy(), Dummy()
    svc.add_focus_object(x)
    svc.add_focus_object(y)
    assert len(svc.trail_ids()) == 2
    svc.clear()
    assert svc.trail_ids() == []
