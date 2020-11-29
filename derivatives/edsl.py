from derivatives.core import AnyChar, Char, Epsilon, Regex


def string(s: str) -> Regex:
    regex: Regex = Epsilon()
    for c in s:
        regex *= Char(c)
    return regex


def any_with(regex: Regex) -> Regex:
    return AnyChar().star() * regex * AnyChar().star()


def any_without(regex: Regex) -> Regex:
    return ~any_with(regex)
