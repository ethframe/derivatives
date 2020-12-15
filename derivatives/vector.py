from typing import List, Optional, Set, Tuple

from .core import EMPTY, Regex
from .partition import CHARSET_END, Partition, make_merge_inplace_fn

VectorItem = Tuple[int, Regex]


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


vector_append = make_merge_inplace_fn(
    vector_append_copy, vector_append_inplace
)


class Vector:
    def __init__(self, items: List[Tuple[int, Regex]]):
        self._items = items

    def tags(self) -> Set[int]:
        return {tag for tag, regex in self._items if regex.nullable()}

    def transitions(self) -> Partition["Vector"]:
        partial: Partition[List[Tuple[int, Regex]]] = [(CHARSET_END, [])]
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
