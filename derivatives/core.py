from typing import Any, List, Tuple

from .partition import CHARSET_END, Partition, make_merge_fn, make_update_fn

Derivatives = Partition['Regex']


def merge_args(left: List['Regex'], right: List['Regex']) -> List['Regex']:
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

    def __str__(self) -> str:
        raise NotImplementedError()

    def nullable(self) -> bool:
        raise NotImplementedError()

    def derivatives(self) -> Derivatives:
        raise NotImplementedError()

    def __mul__(self, other: object) -> 'Regex':
        if isinstance(other, Empty):
            return other
        if isinstance(other, Epsilon):
            return self
        if isinstance(other, Regex):
            return Sequence(self, other)
        return NotImplemented

    def _union_one(self, other: 'Regex') -> 'Regex':
        if self == other:
            return self
        if self < other:
            return Union([self, other])
        return Union([other, self])

    def _union_many(self, other: List['Regex']) -> 'Regex':
        return Union(merge_args([self], other))

    def union(self, other: 'Regex') -> 'Regex':
        return other._union_one(self)

    def __or__(self, other: object) -> 'Regex':
        if isinstance(other, Regex):
            return self.union(other)
        return NotImplemented

    def __and__(self, other: object) -> 'Regex':
        if isinstance(other, Empty):
            return other
        if isinstance(other, Regex):
            if self == other:
                return self
            return Intersect(self, other)
        return NotImplemented

    def __sub__(self, other: object) -> 'Regex':
        if isinstance(other, Empty):
            return self
        if isinstance(other, Regex):
            if self == other:
                return Empty()
            return self & ~other
        return NotImplemented

    def __invert__(self) -> 'Regex':
        if isinstance(self, Invert):
            return self._regex
        return Invert(self)

    def star(self) -> 'Regex':
        if isinstance(self, (Empty, Epsilon, Repeat)):
            return self
        return Repeat(self)

    def plus(self) -> 'Regex':
        return self * self.star()

    def opt(self) -> 'Regex':
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
        val: int = getattr(self, "_hash", None)
        if val is None:
            self._hash = val = hash((id(self.__class__),) + self._key())
        return val


class Empty(Regex):

    def __str__(self) -> str:
        return "\\0"

    def nullable(self) -> bool:
        return False

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

    def __mul__(self, other: object) -> Regex:
        return self

    def _union_one(self, other: 'Regex') -> 'Regex':
        return other

    def _union_many(self, other: List['Regex']) -> 'Regex':
        return Union(other)

    def union(self, other: 'Regex') -> 'Regex':
        return other

    def __and__(self, other: object) -> Regex:
        return self

    def __sub__(self, other: object) -> Regex:
        return self

    def _key(self) -> Tuple[Any, ...]:
        return ()


class Epsilon(Regex):

    def __str__(self) -> str:
        return "\\e"

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

    def __mul__(self, other: object) -> Regex:
        if isinstance(other, Regex):
            return other
        return NotImplemented

    def _key(self) -> Tuple[Any, ...]:
        return ()


class CharRanges(Regex):
    def __init__(self, ranges: List[Tuple[int, int]]):
        self._ranges = ranges

    def __str__(self) -> str:
        def from_code(code: int) -> str:
            char = chr(code)
            if char in "\\{}()+|&~*?.[]":
                return "\\" + char
            return char
        if len(self._ranges) == 1:
            start, end = self._ranges[0]
            if start == 0 and end == CHARSET_END:
                return "."
            if end - start == 1:
                return from_code(start)
        parts = []
        for start, end in self._ranges:
            num = end - start
            if num == 1:
                parts.append(from_code(start))
            elif num == 2:
                parts.append(from_code(start) + from_code(start + 1))
            else:
                parts.append(from_code(start) + '-' + from_code(end - 1))
        return '[' + ''.join(parts) + ']'

    def nullable(self) -> bool:
        return False

    def derivatives(self) -> Derivatives:
        result: Derivatives = []
        last = 0
        for start, end in self._ranges:
            if start > last:
                result.append((start, Empty()))
            result.append((end, Epsilon()))
            last = end
        if CHARSET_END > last:
            result.append((CHARSET_END, Empty()))
        return result

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._ranges,))


def append_item(left: Regex, right: Regex) -> Regex:
    return left * right


append_items = make_update_fn(append_item)


def merge_union_item(left: Regex, right: Regex) -> Regex:
    return left.union(right)


merge_union = make_merge_fn(merge_union_item, merge_union_item)


class Sequence(Regex):

    def __init__(self, first: Regex, second: Regex):
        self._first = first
        self._second = second

    def __str__(self) -> str:
        def maybe_paren(regex: Regex) -> str:
            if isinstance(regex, (Union, Intersect)):
                return "({})".format(regex)
            return str(regex)
        return maybe_paren(self._first) + maybe_paren(self._second)

    def nullable(self) -> bool:
        return self._first.nullable() and self._second.nullable()

    def derivatives(self) -> Derivatives:
        result = append_items(self._first.derivatives(), self._second)
        if self._first.nullable():
            result = merge_union(result, self._second.derivatives())
        return result

    def __mul__(self, other: object) -> Regex:
        return self._first * (self._second * other)

    def _key(self) -> Tuple[Any, ...]:
        return (self._first, self._second)


class Union(Regex):

    def __init__(self, items: List[Regex]):
        self._items = items

    def __str__(self) -> str:
        def maybe_paren(regex: Regex) -> str:
            if isinstance(regex, Intersect):
                return "({})".format(regex)
            return str(regex)
        return "|".join(maybe_paren(item) for item in self._items)

    def nullable(self) -> bool:
        return any(item.nullable() for item in self._items)

    def derivatives(self) -> Derivatives:
        items = iter(self._items)
        result = next(items).derivatives()
        for item in items:
            result = merge_union(result, item.derivatives())
        return result

    def _union_one(self, other: 'Regex') -> 'Regex':
        return Union(merge_args(self._items, [other]))

    def _union_many(self, other: List['Regex']) -> 'Regex':
        return Union(merge_args(self._items, other))

    def union(self, other: 'Regex') -> 'Regex':
        return other._union_many(self._items)

    def _key(self) -> Tuple[Any, ...]:
        return (tuple(self._items),)


def merge_intersect_item(left: Regex, right: Regex) -> Regex:
    return left & right


merge_intersect = make_merge_fn(merge_intersect_item, merge_intersect_item)


class Intersect(Regex):

    def __init__(self, first: Regex, second: Regex):
        self._first = first
        self._second = second

    def __str__(self) -> str:
        def maybe_paren(regex: Regex) -> str:
            if isinstance(regex, Union):
                return "({})".format(regex)
            return str(regex)
        return "{}&{}".format(maybe_paren(self._first),
                              maybe_paren(self._second))

    def nullable(self) -> bool:
        return self._first.nullable() and self._second.nullable()

    def derivatives(self) -> Derivatives:
        return merge_intersect(self._first.derivatives(),
                               self._second.derivatives())

    def _key(self) -> Tuple[Any, ...]:
        return (self._first, self._second)


class Repeat(Regex):

    def __init__(self, regex: Regex):
        self._regex = regex

    def __str__(self) -> str:
        if isinstance(self._regex, (Empty, Epsilon, CharRanges, Repeat)):
            return str(self._regex) + "*"
        return "({})*".format(self._regex)

    def nullable(self) -> bool:
        return True

    def derivatives(self) -> Derivatives:
        return append_items(self._regex.derivatives(), self)

    def _key(self) -> Tuple[Any, ...]:
        return (self._regex,)


class Invert(Regex):

    def __init__(self, regex: Regex):
        self._regex = regex

    def __str__(self) -> str:
        if isinstance(self._regex, (Empty, Epsilon, CharRanges, Invert)):
            return "~" + str(self._regex)
        return "~({})".format(self._regex)

    def nullable(self) -> bool:
        return not self._regex.nullable()

    def derivatives(self) -> Derivatives:
        return [(end, ~item) for end, item in self._regex.derivatives()]

    def _key(self) -> Tuple[Any, ...]:
        return (self._regex,)
