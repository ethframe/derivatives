from typing import List, Optional, Tuple

from .core import EMPTY, EPSILON, CRegex
from .partition import CHARSET_END, Partition, make_merge_fn

VectorItem = Tuple[int, CRegex]


def vector_append_copy(
        left: List[VectorItem],
        right: Optional[VectorItem]) -> List[VectorItem]:
    copy = left.copy()
    if right is not None:
        copy.append(right)
    return copy


def vector_append_inplace(
        left: List[VectorItem],
        right: Optional[VectorItem]) -> List[VectorItem]:
    if right is not None:
        left.append(right)
    return left


vector_append = make_merge_fn(vector_append_inplace, vector_append_copy)


class Vector:
    def __init__(self, items: List[VectorItem]):
        self._items = items

    def tags(self) -> List[int]:
        return [tag for tag, regex in self._items if regex.nullable()]

    def remove_epsilon(self) -> "Vector":
        return Vector(
            [(tag, regex) for tag, regex in self._items if regex != EPSILON]
        )

    def transitions(self) -> Partition["Vector"]:
        partial: Partition[List[VectorItem]] = [(CHARSET_END, [])]
        for tag, item in self._items:
            partial = vector_append(
                partial,
                (
                    (end, None if regex == EMPTY else (tag, regex))
                    for end, regex in item.derivatives()
                )
            )
        return [(end, Vector(items)) for end, items in partial]

    def __hash__(self) -> int:
        return hash(tuple(self._items))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vector):
            return self._items == other._items
        return NotImplemented
