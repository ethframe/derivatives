from derivatives import char, char_range, make_lexer, string


def test_conflicts():
    word = char_range("a", "z").plus()
    num = char_range("0", "9").plus()

    re_a = (word * char(" ")).opt() * string("test")
    re_b = (num * char(" ")).opt() * string("test")
    re_c = string("test test")
    re_d = (num * word * char(" ")) * string("test")
    tokens = [
        ("A", re_a),
        ("B", re_b),
        ("C", re_c),
        ("D", re_d),
    ]

    assert make_lexer(tokens).conflicts() == {('A', 'B'), ('A', 'C')}
