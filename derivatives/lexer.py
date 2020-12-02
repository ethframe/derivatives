from typing import Iterator, List, Tuple

from .core import Regex
from .dfa import Dfa, Vector, make_dfa


def make_lexer(tokens: List[Tuple[str, Regex]]) -> Dfa:
    return make_dfa(Vector(tokens))


def lex_once(dfa: Dfa, string: str) -> Tuple[int, List[str]]:
    runner = dfa.start()
    tag = runner.tags() or []
    pos = 0
    for i, char in enumerate(string):
        if not runner.handle(char):
            break
        tags = runner.tags()
        if tags:
            tag = tags
            pos = i + 1
    return pos, tag


def lex_all(dfa: Dfa, string: str) -> Iterator[Tuple[List[str], str]]:
    while string:
        pos, tag = lex_once(dfa, string)
        yield tag, string[:pos]
        string = string[pos:]
