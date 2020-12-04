from typing import Any, List, Optional, Set, Tuple

from .partition import CHARSET_END, Partition, make_merge_fn

Ranges = Partition[bool]
Derivatives = Partition["Regex"]


def merge_args(left: List["Regex"], right: List["Regex"]) -> List["Regex"]:
    result: List[Regex] = []
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


class Regex:

    def nullable(self) -> bool:
        raise NotImplementedError()

    def derivatives(self) -> Derivatives:
        raise NotImplementedError()

    def tags(self) -> Set[int]:
        raise NotImplementedError()

    def join(self, other: "Regex") -> "Regex":
        return Sequence(self, other)

    def __mul__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return self.join(other)
        return NotImplemented

    def _union_char_class(self, other: Ranges) -> "Regex":
        return UnionCharClass(other, self)

    def _union_one(self, other: "Regex") -> "Regex":
        if self == other:
            return self
        if self < other:
            return Union([self, other])
        return Union([other, self])

    def _union_many(self, other: List["Regex"]) -> "Regex":
        return Union(merge_args([self], other))

    def union(self, other: "Regex") -> "Regex":
        return other._union_one(self)

    def __or__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return self.union(other)
        return NotImplemented

    def _intersect_one(self, other: "Regex") -> "Regex":
        if self == other:
            return self
        if self < other:
            return Intersect([self, other])
        return Intersect([other, self])

    def _intersect_many(self, other: List["Regex"]) -> "Regex":
        return Intersect(merge_args([self], other))

    def intersect(self, other: "Regex") -> "Regex":
        return other._intersect_one(self)

    def __and__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return self.intersect(other)
        return NotImplemented

    def __sub__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return self & ~other
        return NotImplemented

    def __invert__(self) -> "Regex":
        return Invert(self)

    def star(self) -> "Regex":
        return Repeat(self)

    def plus(self) -> "Regex":
        return self.join(self.star())

    def opt(self) -> "Regex":
        return self._union_one(Epsilon())

    def _key(self) -> Tuple[Any, ...]:
        raise NotImplementedError()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Regex):
            return type(self) is type(other) and self._key() == other._key()
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Regex):
            return id(type(self)) < id(type(other)) or \
                type(self) is type(other) and self._key() < other._key()
        return NotImplemented

    def __hash__(self) -> int:
        val: Optional[int] = getattr(self, "_hash", None)
        if val is None:
            self._hash = val = hash((id(self.__class__),) + self._key())
        return val


class Empty(Regex):

    def nullable(self) -> bool:
        return False

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

    def tags(self) -> Set[int]:
        return set()

    def join(self, other: Regex) -> Regex:
        return self

    def _union_one(self, other: Regex) -> Regex:
        return other

    def _union_many(self, other: List[Regex]) -> Regex:
        return Union(other)

    def union(self, other: Regex) -> Regex:
        return other

    def _intersect_one(self, other: Regex) -> Regex:
        return self

    def _intersect_many(self, other: List[Regex]) -> Regex:
        return self

    def intersect(self, other: Regex) -> Regex:
        return self

    def star(self) -> Regex:
        return Epsilon()

    def plus(self) -> Regex:
        return self

    def opt(self) -> Regex:
        return Epsilon()

    def _key(self) -> Tuple[Any, ...]:
        return ()


class Epsilon(Regex):

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

    def tags(self) -> Set[int]:
        return set()

    def join(self, other: Regex) -> Regex:
        return other

    def star(self) -> Regex:
        return self

    def plus(self) -> Regex:
        return self

    def opt(self) -> Regex:
        return self

    def _key(self) -> Tuple[Any, ...]:
        return ()


merge_char_class = make_merge_fn(bool.__or__, bool.__or__)


class CharClass(Regex):

    def __init__(self, ranges: Ranges):
        self._ranges = ranges

    def nullable(self) -> bool:
        return False

    def derivatives(self) -> Derivatives:
        epsilon = Epsilon()
        empty = Empty()
        return [(end, epsilon if pos else empty) for end, pos in self._ranges]

    def tags(self) -> Set[int]:
        return set()

    def _union_char_class(self, other: Ranges) -> Regex:
        return CharClass(merge_char_class(self._ranges, other))

    def _union_one(self, other: Regex) -> Regex:
        return UnionCharClass(self._ranges, other)

    def _union_many(self, other: List[Regex]) -> Regex:
        return UnionCharClass(self._ranges, Union(other))

    def union(self, other: Regex) -> Regex:
        return other._union_char_class(self._ranges)

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._ranges,))


def merge_union_item(left: Regex, right: Regex) -> Regex:
    return left.union(right)


merge_union = make_merge_fn(merge_union_item, merge_union_item)


class Sequence(Regex):

    def __init__(self, first: Regex, second: Regex):
        self._first = first
        self._second = second

    def nullable(self) -> bool:
        return self._first.nullable() and self._second.nullable()

    def derivatives(self) -> Derivatives:
        result = [
            (end, item.join(self._second))
            for end, item in self._first.derivatives()
        ]
        if self._first.nullable():
            result = merge_union(result, self._second.derivatives())
        return result

    def tags(self) -> Set[int]:
        tags = self._first.tags()
        if self._first.nullable():
            tags.update(self._second.tags())
        return tags

    def join(self, other: Regex) -> Regex:
        return Sequence(self._first, self._second.join(other))

    def _key(self) -> Tuple[Any, ...]:
        return (self._first, self._second)


class Union(Regex):

    def __init__(self, items: List[Regex]):
        self._items = items

    def nullable(self) -> bool:
        return any(item.nullable() for item in self._items)

    def derivatives(self) -> Derivatives:
        items = iter(self._items)
        result = next(items).derivatives()
        for item in items:
            result = merge_union(result, item.derivatives())
        return result

    def tags(self) -> Set[int]:
        items = iter(self._items)
        tags = next(items).tags()
        for item in items:
            tags.update(item.tags())
        return tags

    def _union_char_class(self, other: Ranges) -> Regex:
        return UnionCharClass(other, self)

    def _union_one(self, other: Regex) -> Regex:
        return Union(merge_args(self._items, [other]))

    def _union_many(self, other: List[Regex]) -> Regex:
        return Union(merge_args(self._items, other))

    def union(self, other: Regex) -> Regex:
        return other._union_many(self._items)

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._items),)


def merge_union_char_class_item(left: Regex, right: bool) -> Regex:
    return left.union(Epsilon()) if right else left


merge_union_char_class = make_merge_fn(merge_union_char_class_item,
                                       merge_union_char_class_item)


class UnionCharClass(Regex):

    def __init__(self, ranges: Ranges, regex: Regex):
        self._ranges = ranges
        self._regex = regex

    def nullable(self) -> bool:
        return self._regex.nullable()

    def derivatives(self) -> Derivatives:
        return merge_union_char_class(self._regex.derivatives(), self._ranges)

    def tags(self) -> Set[int]:
        return self._regex.tags()

    def _union_char_class(self, other: Ranges) -> Regex:
        return UnionCharClass(merge_char_class(self._ranges, other),
                              self._regex)

    def _union_one(self, other: Regex) -> Regex:
        return UnionCharClass(self._ranges, self._regex._union_one(other))

    def _union_many(self, other: List[Regex]) -> Regex:
        return UnionCharClass(self._ranges, self._regex._union_many(other))

    def union(self, other: Regex) -> Regex:
        return self._regex.union(other._union_char_class(self._ranges))

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._ranges), self._regex)


def merge_intersect_item(left: Regex, right: Regex) -> Regex:
    return left.intersect(right)


merge_intersect = make_merge_fn(merge_intersect_item, merge_intersect_item)


class Intersect(Regex):

    def __init__(self, items: List[Regex]):
        self._items = items

    def nullable(self) -> bool:
        return all(item.nullable() for item in self._items)

    def derivatives(self) -> Derivatives:
        items = iter(self._items)
        result = next(items).derivatives()
        for item in items:
            result = merge_intersect(result, item.derivatives())
        return result

    def tags(self) -> Set[int]:
        items = iter(self._items)
        tags = next(items).tags()
        for item in items:
            tags.intersection_update(item.tags())
        return tags

    def _intersect_one(self, other: Regex) -> Regex:
        return Intersect(merge_args(self._items, [other]))

    def _intersect_many(self, other: List[Regex]) -> Regex:
        return Intersect(merge_args(self._items, other))

    def intersect(self, other: Regex) -> Regex:
        return other._intersect_many(self._items)

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._items),)


class Repeat(Regex):

    def __init__(self, regex: Regex):
        self._regex = regex

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [
            (end, item.join(self)) for end, item in self._regex.derivatives()
        ]

    def tags(self) -> Set[int]:
        return self._regex.tags()

    def star(self) -> Regex:
        return self

    def plus(self) -> Regex:
        return self

    def opt(self) -> Regex:
        return self

    def _key(self) -> Tuple[Any, ...]:
        return (self._regex,)


class Invert(Regex):

    def __init__(self, regex: Regex):
        self._regex = regex

    def nullable(self) -> bool:
        return not self._regex.nullable()

    def derivatives(self) -> Derivatives:
        return [(end, ~item) for end, item in self._regex.derivatives()]

    def tags(self) -> Set[int]:
        return set()

    def __invert__(self) -> Regex:
        return self._regex

    def _key(self) -> Tuple[Any, ...]:
        return (self._regex,)


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
