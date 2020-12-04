from .core import Derivatives, Empty, Epsilon, Precomputed, Regex
from .partition import CHARSET_END


def epsilon() -> Regex:
    return Epsilon()


def any_char() -> Regex:
    return Precomputed([(CHARSET_END, Epsilon())])


def char(char: str) -> Regex:
    return char_range(char, char)


def char_set(chars: str) -> Regex:
    derivatives: Derivatives = []
    end = 0
    for char in sorted(chars):
        code = ord(char)
        if code == end:
            end += 1
        else:
            if end != 0:
                derivatives.append((end, Epsilon()))
            derivatives.append((code, Empty()))
            end = code + 1
    derivatives.append((end, Epsilon()))
    if end != CHARSET_END:
        derivatives.append((CHARSET_END, Empty()))
    return Precomputed(derivatives)


def char_range(start: str, end: str) -> Regex:
    derivatives: Derivatives = []
    code = ord(start)
    if code != 0:
        derivatives.append((code, Empty()))
    code = ord(end) + 1
    derivatives.append((code, Epsilon()))
    if code != CHARSET_END:
        derivatives.append((CHARSET_END, Empty()))
    return Precomputed(derivatives)


def string(s: str) -> Regex:
    regex: Regex = Epsilon()
    for c in s:
        regex *= char(c)
    return regex


def any_with(regex: Regex) -> Regex:
    return any_char().star() * regex * any_char().star()


def any_without(regex: Regex) -> Regex:
    return ~any_with(regex)
