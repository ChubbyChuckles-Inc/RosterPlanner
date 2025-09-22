from gui.services.multi_column_sort import MultiColumnSorter, SortKey


def test_single_key_ascending():
    data = [5, 1, 3]
    sorter = MultiColumnSorter(data)
    assert sorter.sort([SortKey(lambda x: x, True)]) == [1, 3, 5]


def test_single_key_descending():
    data = [5, 1, 3]
    sorter = MultiColumnSorter(data)
    assert sorter.sort([SortKey(lambda x: x, False)]) == [5, 3, 1]


def test_multi_key_stability():
    rows = [
        {"points": 10, "name": "B"},
        {"points": 12, "name": "A"},
        {"points": 10, "name": "A"},
    ]
    sorter = MultiColumnSorter(rows)
    sorted_rows = sorter.sort(
        [
            SortKey(lambda r: r["points"], False),
            SortKey(lambda r: r["name"], True),
        ]
    )
    # Expect points descending, then name ascending within same points
    assert [r["points"] for r in sorted_rows] == [12, 10, 10]
    assert [r["name"] for r in sorted_rows] == ["A", "A", "B"]
