import sys

from .charset import parse_char_set
from .core import EMPTY, EPSILON, CRegex
from .utf8 import utf8_range_regex


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
    return Regex(utf8_range_regex(0, sys.maxunicode))


def char(char: str) -> Regex:
    return Regex(utf8_range_regex(ord(char), ord(char)))


def char_set(chars: str) -> Regex:
    regex: CRegex = EMPTY
    for start, end in parse_char_set(chars):
        regex = regex.union(utf8_range_regex(start, end))
    return Regex(regex)


def string(s: str) -> Regex:
    regex: CRegex = EPSILON
    for c in s:
        regex = regex.join(utf8_range_regex(ord(c), ord(c)))
    return Regex(regex)


def any_with(regex: Regex) -> Regex:
    return any_char().star() * regex * any_char().star()


def any_without(regex: Regex) -> Regex:
    return ~any_with(regex)
