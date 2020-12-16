from .core import EMPTY, EPSILON, CharClass, CRegex, Ranges, Tag
from .partition import CHARSET_END


class Regex:
    def __init__(self, regex: CRegex):
        self._regex = regex

    def getvalue(self) -> CRegex:
        return self._regex

    def __mul__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return Regex(self._regex.join(other._regex))
        return NotImplemented

    def __or__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return Regex(self._regex.union(other._regex))
        return NotImplemented

    def __and__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return Regex(self._regex.intersect(other._regex))
        return NotImplemented

    def __sub__(self, other: object) -> "Regex":
        if isinstance(other, Regex):
            return Regex(self._regex.intersect(other._regex.invert()))
        return NotImplemented

    def __invert__(self) -> "Regex":
        return Regex(self._regex.invert())

    def star(self) -> "Regex":
        return Regex(self._regex.repeat())

    def plus(self) -> "Regex":
        return Regex(self._regex.join(self._regex.repeat()))

    def opt(self) -> "Regex":
        return Regex(self._regex.union(EPSILON))


def empty() -> Regex:
    return Regex(EMPTY)


def epsilon() -> Regex:
    return Regex(EPSILON)


def any_char() -> Regex:
    return Regex(CharClass([(CHARSET_END, True)]))


def char(char: str) -> Regex:
    return char_range(char, char)


def char_set(chars: str) -> Regex:
    ranges: Ranges = []
    end = 0
    for char in sorted(chars):
        code = ord(char)
        if code == end:
            end += 1
        else:
            if end != 0:
                ranges.append((end, True))
            ranges.append((code, False))
            end = code + 1
    ranges.append((end, True))
    if end != CHARSET_END:
        ranges.append((CHARSET_END, False))
    return Regex(CharClass(ranges))


def char_range(start: str, end: str) -> Regex:
    ranges: Ranges = []
    code = ord(start)
    if code != 0:
        ranges.append((code, False))
    code = ord(end) + 1
    ranges.append((code, True))
    if code != CHARSET_END:
        ranges.append((CHARSET_END, False))
    return Regex(CharClass(ranges))


def string(s: str) -> Regex:
    regex: Regex = Regex(EPSILON)
    for c in s:
        regex *= char(c)
    return regex


def any_with(regex: Regex) -> Regex:
    return any_char().star() * regex * any_char().star()


def any_without(regex: Regex) -> Regex:
    return ~any_with(regex)


def tag(value: int) -> Regex:
    return Regex(Tag(value))
