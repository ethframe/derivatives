from .core import Empty, Tag
from .dfa import DFA


def make_lexer(tokens):
    regex = Empty()
    parts = Empty()
    for name, tok in tokens:
        tok = DFA.from_regex(tok)
        regex |= DFA.from_regex(((tok - parts) * Tag(name)))
        parts |= tok
    return DFA.from_regex(regex)


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
            return pos, tag
    return pos, tag


def lex_all(regex, string):
    while string:
        pos, tag = lex_once(regex, string)
        yield tag, string[:pos]
        string = string[pos:]
