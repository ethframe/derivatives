from typing import Any, List, Set, Tuple

from .core import Derivatives, Empty, Regex
from .partition import CHARSET_END, Partition, make_merge_fn


class Tag(Regex):
    def __init__(self, tag: int):
        self._tag = tag

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

    def tags(self) -> Set[int]:
        return {self._tag}

    def _key(self) -> Tuple[Any, ...]:
        return (self._tag,)


def merge_partial_item(acc: List[Regex], val: Regex) -> List[Regex]:
    acc_copy = acc.copy()
    acc_copy.append(val)
    return acc_copy


def merge_partial_item_inplace(acc: List[Regex], val: Regex) -> List[Regex]:
    acc.append(val)
    return acc


merge_partial = make_merge_fn(merge_partial_item, merge_partial_item_inplace)


class Vector(Regex):

    def __init__(self, items: List[Regex]):
        self._items = items

    def nullable(self) -> bool:
        return any(regex.nullable() for regex in self._items)

    def derivatives(self) -> Derivatives:
        partial: Partition[List[Regex]] = [(CHARSET_END, [])]
        for item in self._items:
            partial = merge_partial(partial, item.derivatives())
        return [(end, make_vector(items)) for end, items in partial]

    def tags(self) -> Set[int]:
        tags: Set[int] = set()
        for regex in self._items:
            tags.update(regex.tags())
        return tags

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._items),)


def make_vector(items: List[Regex]) -> Regex:
    items = [item for item in items if not isinstance(item, Empty)]
    if len(items) == 0:
        return Empty()
    if len(items) == 1:
        return items[0]
    return Vector(items)
