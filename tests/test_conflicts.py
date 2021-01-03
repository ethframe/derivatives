from typing import Dict, Set

from derivatives import char, char_set, make_lexer, string
from derivatives.lexer import select_first


def test_conflicts():
    word = char_set("a-z").plus()
    num = char_set("0-9").plus()

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

    conflicts = set()

    def collect_conflicts(tags: Set[int], names: Dict[int, str]) -> str:
        if len(tags) > 1:
            conflicts.add(tuple(sorted(names[tag] for tag in tags)))
        return select_first(tags, names)

    make_lexer(tokens, collect_conflicts)
    assert conflicts == {('A', 'B'), ('A', 'C')}
