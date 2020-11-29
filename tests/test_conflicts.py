from derivatives import DFA, Char, CharRange, Tag, string


def test_conflicts():
    word = CharRange("a", "z").plus()
    num = CharRange("0", "9").plus()

    re_a = (word * Char(" ")).opt() * string("test")
    re_b = (num * Char(" ")).opt() * string("test")
    re_c = string("test test")
    re_d = (num * word * Char(" ")) * string("test")
    comm = (re_a * Tag("A") | re_b * Tag("B") |
            re_c * Tag("C") | re_d * Tag("D"))
    assert DFA.from_regex(comm).conflicts() == {('A', 'B'), ('A', 'C')}
