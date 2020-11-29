from derivatives.core import AnyChar, Char, Epsilon


def string(s):
    regex = Epsilon()
    for c in s:
        regex *= Char(c)
    return regex


def any_with(regex):
    return AnyChar().star() * regex * AnyChar().star()


def any_without(regex):
    return ~any_with(regex)
