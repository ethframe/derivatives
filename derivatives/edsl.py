from .core import CharClass, Empty, Epsilon, Ranges, Regex, Tag
from .partition import CHARSET_END


def empty() -> Regex:
    return Empty()


def epsilon() -> Regex:
    return Epsilon()


def any_char() -> Regex:
    return CharClass([(CHARSET_END, True)])


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
    return CharClass(ranges)


def char_range(start: str, end: str) -> Regex:
    ranges: Ranges = []
    code = ord(start)
    if code != 0:
        ranges.append((code, False))
    code = ord(end) + 1
    ranges.append((code, True))
    if code != CHARSET_END:
        ranges.append((CHARSET_END, False))
    return CharClass(ranges)


def string(s: str) -> Regex:
    regex: Regex = Epsilon()
    for c in s:
        regex *= char(c)
    return regex


def any_with(regex: Regex) -> Regex:
    return any_char().star() * regex * any_char().star()


def any_without(regex: Regex) -> Regex:
    return ~any_with(regex)


def tag(value: int) -> Regex:
    return Tag(value)
