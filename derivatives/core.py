from typing import Any, List, Set, Tuple

from .partition import CHARSET_END, Partition, make_merge_copy_fn

Ranges = Partition[bool]
Derivatives = Partition["CRegex"]


def merge_args(left: List["CRegex"], right: List["CRegex"]) -> List["CRegex"]:
    result: List[CRegex] = []
    lit = iter(left)
    rit = iter(right)
    lval = next(lit, None)
    rval = next(rit, None)
    while lval is not None and rval is not None:
        if lval == rval:
            result.append(lval)
            lval = next(lit, None)
            rval = next(rit, None)
        elif lval < rval:
            result.append(lval)
            lval = next(lit, None)
        else:
            result.append(rval)
            rval = next(rit, None)
    if lval is not None:
        result.append(lval)
        result.extend(lit)
    elif rval is not None:
        result.append(rval)
        result.extend(rit)
    return result


KIND_EMPTY = 0
KIND_EPSILON = 1
KIND_CHAR_CLASS = 2
KIND_SEQUENCE = 3
KIND_UNION = 4
KIND_UNION_CHAR_CLASS = 5
KIND_INTERSECT = 6
KIND_REPEAT = 7
KIND_INVERT = 8
KIND_TAG = 9


class CRegex:

    _kind: int

    def __init__(self, key: Tuple[Any, ...]):
        self._key = (self._kind, *key)
        self._hash = hash(self._key)

    def nullable(self) -> bool:
        raise NotImplementedError()

    def derivatives(self) -> Derivatives:
        raise NotImplementedError()

    def tags(self) -> Set[int]:
        raise NotImplementedError()

    def join(self, other: "CRegex") -> "CRegex":
        return Sequence(self, other)

    def _union_char_class(self, other: Ranges) -> "CRegex":
        return UnionCharClass(other, self)

    def _union_one(self, other: "CRegex") -> "CRegex":
        if self == other:
            return self
        if self < other:
            return Union([self, other])
        return Union([other, self])

    def _union_many(self, other: List["CRegex"]) -> "CRegex":
        return Union(merge_args([self], other))

    def union(self, other: "CRegex") -> "CRegex":
        return other._union_one(self)

    def _intersect_one(self, other: "CRegex") -> "CRegex":
        if self == other:
            return self
        if self < other:
            return Intersect([self, other])
        return Intersect([other, self])

    def _intersect_many(self, other: List["CRegex"]) -> "CRegex":
        return Intersect(merge_args([self], other))

    def intersect(self, other: "CRegex") -> "CRegex":
        return other._intersect_one(self)

    def invert(self) -> "CRegex":
        return Invert(self)

    def repeat(self) -> "CRegex":
        return Repeat(self)

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if isinstance(other, CRegex):
            return self._key == other._key
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, CRegex):
            return self._key < other._key
        return NotImplemented

    def __hash__(self) -> int:
        return self._hash


class Empty(CRegex):

    _kind = KIND_EMPTY

    def __init__(self) -> None:
        super().__init__(())

    def nullable(self) -> bool:
        return False

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, self)]

    def tags(self) -> Set[int]:
        return set()

    def join(self, other: CRegex) -> CRegex:
        return self

    def _union_char_class(self, other: Ranges) -> CRegex:
        return CharClass(other)

    def _union_one(self, other: CRegex) -> CRegex:
        return other

    def _union_many(self, other: List[CRegex]) -> CRegex:
        return Union(other)

    def union(self, other: CRegex) -> CRegex:
        return other

    def _intersect_one(self, other: CRegex) -> CRegex:
        return self

    def _intersect_many(self, other: List[CRegex]) -> CRegex:
        return self

    def intersect(self, other: CRegex) -> CRegex:
        return self

    def repeat(self) -> CRegex:
        return EPSILON


EMPTY = Empty()


class Epsilon(CRegex):

    _kind = KIND_EPSILON

    def __init__(self) -> None:
        super().__init__(())

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, EMPTY)]

    def tags(self) -> Set[int]:
        return set()

    def join(self, other: CRegex) -> CRegex:
        return other

    def repeat(self) -> CRegex:
        return self


EPSILON = Epsilon()


union_ranges = make_merge_copy_fn(bool.__or__)


class CharClass(CRegex):

    _kind = KIND_CHAR_CLASS

    def __init__(self, ranges: Ranges):
        self._ranges = ranges
        super().__init__(tuple(ranges))

    def nullable(self) -> bool:
        return False

    def derivatives(self) -> Derivatives:
        return [(end, EPSILON if pos else EMPTY) for end, pos in self._ranges]

    def tags(self) -> Set[int]:
        return set()

    def _union_char_class(self, other: Ranges) -> CRegex:
        return CharClass(union_ranges(self._ranges, other))

    def _union_one(self, other: CRegex) -> CRegex:
        return UnionCharClass(self._ranges, other)

    def _union_many(self, other: List[CRegex]) -> CRegex:
        return UnionCharClass(self._ranges, Union(other))

    def union(self, other: CRegex) -> CRegex:
        return other._union_char_class(self._ranges)


def union_regexes_items(left: CRegex, right: CRegex) -> CRegex:
    return left.union(right)


union_regexes = make_merge_copy_fn(union_regexes_items)


class Sequence(CRegex):

    _kind = KIND_SEQUENCE

    def __init__(self, first: CRegex, second: CRegex):
        self._first = first
        self._second = second
        super().__init__((first, second))

    def nullable(self) -> bool:
        return self._first.nullable() and self._second.nullable()

    def derivatives(self) -> Derivatives:
        result = [
            (end, item.join(self._second))
            for end, item in self._first.derivatives()
        ]
        if self._first.nullable():
            result = union_regexes(result, self._second.derivatives())
        return result

    def tags(self) -> Set[int]:
        tags = self._first.tags()
        if self._first.nullable():
            tags.update(self._second.tags())
        return tags

    def join(self, other: CRegex) -> CRegex:
        return Sequence(self._first, self._second.join(other))


class Union(CRegex):

    _kind = KIND_UNION

    def __init__(self, items: List[CRegex]):
        self._items = items
        super().__init__(tuple(items))

    def nullable(self) -> bool:
        return any(item.nullable() for item in self._items)

    def derivatives(self) -> Derivatives:
        items = iter(self._items)
        result = next(items).derivatives()
        for item in items:
            result = union_regexes(result, item.derivatives())
        return result

    def tags(self) -> Set[int]:
        items = iter(self._items)
        tags = next(items).tags()
        for item in items:
            tags.update(item.tags())
        return tags

    def _union_char_class(self, other: Ranges) -> CRegex:
        return UnionCharClass(other, self)

    def _union_one(self, other: CRegex) -> CRegex:
        return Union(merge_args(self._items, [other]))

    def _union_many(self, other: List[CRegex]) -> CRegex:
        return Union(merge_args(self._items, other))

    def union(self, other: CRegex) -> CRegex:
        return other._union_many(self._items)


def union_regex_ranges_item(left: CRegex, right: bool) -> CRegex:
    return left.union(EPSILON) if right else left


union_regex_ranges = make_merge_copy_fn(union_regex_ranges_item)


class UnionCharClass(CRegex):

    _kind = KIND_UNION_CHAR_CLASS

    def __init__(self, ranges: Ranges, regex: CRegex):
        self._ranges = ranges
        self._regex = regex
        super().__init__((tuple(ranges), regex))

    def nullable(self) -> bool:
        return self._regex.nullable()

    def derivatives(self) -> Derivatives:
        return union_regex_ranges(self._regex.derivatives(), self._ranges)

    def tags(self) -> Set[int]:
        return self._regex.tags()

    def _union_char_class(self, other: Ranges) -> CRegex:
        return UnionCharClass(union_ranges(self._ranges, other),
                              self._regex)

    def _union_one(self, other: CRegex) -> CRegex:
        return UnionCharClass(self._ranges, self._regex._union_one(other))

    def _union_many(self, other: List[CRegex]) -> CRegex:
        return UnionCharClass(self._ranges, self._regex._union_many(other))

    def union(self, other: CRegex) -> CRegex:
        return self._regex.union(other._union_char_class(self._ranges))


def intersect_regexes_item(left: CRegex, right: CRegex) -> CRegex:
    return left.intersect(right)


intersect_regexes = make_merge_copy_fn(intersect_regexes_item)


class Intersect(CRegex):

    _kind = KIND_INTERSECT

    def __init__(self, items: List[CRegex]):
        self._items = items
        super().__init__(tuple(items))

    def nullable(self) -> bool:
        return all(item.nullable() for item in self._items)

    def derivatives(self) -> Derivatives:
        items = iter(self._items)
        result = next(items).derivatives()
        for item in items:
            result = intersect_regexes(result, item.derivatives())
        return result

    def tags(self) -> Set[int]:
        items = iter(self._items)
        tags = next(items).tags()
        for item in items:
            tags.intersection_update(item.tags())
        return tags

    def _intersect_one(self, other: CRegex) -> CRegex:
        return Intersect(merge_args(self._items, [other]))

    def _intersect_many(self, other: List[CRegex]) -> CRegex:
        return Intersect(merge_args(self._items, other))

    def intersect(self, other: CRegex) -> CRegex:
        return other._intersect_many(self._items)


class Repeat(CRegex):

    _kind = KIND_REPEAT

    def __init__(self, regex: CRegex):
        self._regex = regex
        super().__init__((regex,))

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [
            (end, item.join(self)) for end, item in self._regex.derivatives()
        ]

    def tags(self) -> Set[int]:
        return self._regex.tags()

    def repeat(self) -> CRegex:
        return self


class Invert(CRegex):

    _kind = KIND_INVERT

    def __init__(self, regex: CRegex):
        self._regex = regex
        super().__init__((regex,))

    def nullable(self) -> bool:
        return not self._regex.nullable()

    def derivatives(self) -> Derivatives:
        return [
            (end, item.invert()) for end, item in self._regex.derivatives()
        ]

    def tags(self) -> Set[int]:
        return set()

    def invert(self) -> CRegex:
        return self._regex


class Tag(CRegex):

    _kind = KIND_TAG

    def __init__(self, tag: int):
        self._tag = tag
        super().__init__((tag,))

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, EMPTY)]

    def tags(self) -> Set[int]:
        return {self._tag}
