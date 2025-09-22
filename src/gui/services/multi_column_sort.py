"""Multi-column sorting utility (Milestone 5.3.1).

Provides a stable multi-key sorting mechanism for tabular view models.
The `MultiColumnSorter` accepts a list of row objects and can sort them
according to a priority list of (key_func, ascending) tuples. Sorting is
stable and applies keys from lowest precedence to highest (like Python's
sorted with chained keys) to keep logic simple and testable.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")
KeyFunc = Callable[[T], object]


@dataclass(frozen=True)
class SortKey:
    key_func: KeyFunc
    ascending: bool = True


class MultiColumnSorter(Generic[T]):
    """Utility to apply multi-key sorting in a stable manner.

    Usage:
        sorter = MultiColumnSorter(rows)
        rows_sorted = sorter.sort([
            SortKey(lambda r: r.points, ascending=False),
            SortKey(lambda r: r.team_name, ascending=True),
        ])
    """

    def __init__(self, rows: Iterable[T]):
        self._rows: List[T] = list(rows)

    def sort(self, keys: Sequence[SortKey]) -> List[T]:
        # Apply from lowest precedence to highest for stability
        result = list(self._rows)
        for sk in reversed(keys):
            result.sort(key=sk.key_func, reverse=not sk.ascending)
        return result

    @staticmethod
    def single(rows: Iterable[T], key: KeyFunc, ascending: bool = True) -> List[T]:
        return sorted(rows, key=key, reverse=not ascending)
