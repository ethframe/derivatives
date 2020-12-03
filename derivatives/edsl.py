from .core import CharRanges, Epsilon, Regex
from .partition import CHARSET_END


def epsilon() -> Regex:
    return Epsilon()


def any_char() -> Regex:
    return CharRanges([(0, CHARSET_END)])


def char(char: str) -> Regex:
    code = ord(char)
    return CharRanges([(code, code + 1)])


def char_set(chars: str) -> Regex:
    ranges = []
    last_end = None
    for char in sorted(chars):
        code = ord(char)
        if last_end and last_end == code:
            last_end = code + 1
            ranges[-1] = (ranges[-1][0], last_end)
        else:
            last_end = code + 1
            ranges.append((code, last_end))
    return CharRanges(ranges)


def char_range(start: str, end: str) -> Regex:
    return CharRanges([(ord(start), ord(end) + 1)])


def string(s: str) -> Regex:
    regex: Regex = Epsilon()
    for c in s:
        regex *= char(c)
    return regex


def any_with(regex: Regex) -> Regex:
    return any_char().star() * regex * any_char().star()


def any_without(regex: Regex) -> Regex:
    return ~any_with(regex)
