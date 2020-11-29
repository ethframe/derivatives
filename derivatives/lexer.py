from .core import Empty
from .dfa import DFA, Vector


def make_lexer(tokens):
    return DFA.from_vector(Vector(tokens))


def lex_once(regex, string):
    tag = regex.tags()
    pos = 0
    for i, char in enumerate(string):
        regex = regex.derive(char)
        tags = regex.tags()
        if tags:
            tag = tags
            pos = i + 1
        if isinstance(regex, Empty):
            break
    return pos, tag


def lex_all(regex, string):
    while string:
        pos, tag = lex_once(regex, string)
        yield tag, string[:pos]
        string = string[pos:]
