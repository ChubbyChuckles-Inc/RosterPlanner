import pytest

from gui.design.accessible_reorder import (
    move_up,
    move_down,
    move_top,
    move_bottom,
    move_to,
    move_after,
    ReorderList,
    interpret_key_command,
)


@pytest.fixture
def sample():
    return ["A", "B", "C", "D"]


def test_move_up_basic(sample):
    r = move_up(sample, 2)
    assert r.changed is True
    assert list(r.items) == ["A", "C", "B", "D"]
    assert r.focus_index == 1


def test_move_up_top_noop(sample):
    r = move_up(sample, 0)
    assert r.changed is False
    assert list(r.items) == sample


def test_move_down_basic(sample):
    r = move_down(sample, 1)
    assert r.changed is True
    assert list(r.items) == ["A", "C", "B", "D"]
    assert r.focus_index == 2


def test_move_down_bottom_noop(sample):
    r = move_down(sample, 3)
    assert r.changed is False
    assert list(r.items) == sample


def test_move_top(sample):
    r = move_top(sample, 2)
    assert r.changed is True
    assert list(r.items) == ["C", "A", "B", "D"]
    assert r.focus_index == 0


def test_move_bottom(sample):
    r = move_bottom(sample, 1)
    assert r.changed is True
    assert list(r.items) == ["A", "C", "D", "B"]
    assert r.focus_index == 3


def test_move_to_same_index_noop(sample):
    r = move_to(sample, 1, 1)
    assert r.changed is False
    assert list(r.items) == sample


def test_move_to(sample):
    r = move_to(sample, 3, 1)
    assert r.changed is True
    assert list(r.items) == ["A", "D", "B", "C"]
    assert r.focus_index == 1


def test_move_after(sample):
    r = move_after(sample, 0, 2)  # move A after C
    assert r.changed is True
    assert list(r.items) == ["B", "C", "A", "D"]
    assert r.focus_index == 2


def test_move_after_adjacent_noop(sample):
    r = move_after(sample, 2, 1)  # after_index immediately before index
    assert r.changed is False
    assert list(r.items) == sample


def test_reorder_list_facade(sample):
    rl = ReorderList(sample)
    res1 = rl.op_move_down(0)
    assert list(rl.items) == ["B", "A", "C", "D"]
    assert res1.changed
    res2 = rl.op_move_top(2)  # move C to top
    assert list(rl.items) == ["C", "B", "A", "D"]
    assert res2.focus_index == 0


def test_interpret_key_command():
    assert interpret_key_command("ArrowUp") == "up"
    assert interpret_key_command("ctrl+home") == "top"
    assert interpret_key_command("nope") == ""


def test_integrity_no_duplicates(sample):
    r = move_bottom(sample, 0)
    assert sorted(r.items) == sorted(sample)
    assert len(set(r.items)) == len(sample)
