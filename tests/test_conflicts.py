from derivatives.lexer import make_lexer
from derivatives import Char, CharRange, string


def test_conflicts():
    word = CharRange("a", "z").plus()
    num = CharRange("0", "9").plus()

    re_a = (word * Char(" ")).opt() * string("test")
    re_b = (num * Char(" ")).opt() * string("test")
    re_c = string("test test")
    re_d = (num * word * Char(" ")) * string("test")
    tokens = [
        ("A", re_a),
        ("B", re_b),
        ("C", re_c),
        ("D", re_d),
    ]

    assert make_lexer(tokens).conflicts() == {('A', 'B'), ('A', 'C')}
