import pytest

from derivatives import (
    AnyChar, Char, CharRange, CharSet, any_without, lex_all, make_lexer, string
)


@pytest.fixture
def c_tokens():
    # Adapted from http://www.quut.com/c/ANSI-C-grammar-l.html
    O = CharRange("0", "7")
    D = CharRange("0", "9")
    NZ = CharRange("1", "9")
    L = CharRange("a", "z") | CharRange("A", "Z") | Char("_")
    A = L | D
    H = CharRange("a", "f") | CharRange("A", "F") | D
    HP = Char("0") * CharSet("xX")
    E = CharSet("Ee") * CharSet("+-").opt() * D.plus()
    P = CharSet("Pp") * CharSet("+-").opt() * D.plus()
    FS = CharSet("fFlL")
    IS = CharSet("uU") * (CharSet("lL") | string("ll") |
                          string("LL")).opt() | \
        (CharSet("lL") | string("ll") | string("LL")) * CharSet("uU").opt()
    CP = CharSet("uUL")
    SP = string("u8") | CP
    ES = Char("\\") * (CharSet("'\"?\\abfnrtv") | O | O * O | O * O * O |
                       Char("x") * H.plus())
    WS = CharSet(" \t\v\n\f")

    tokens = [
        ("comment", string("/*") * any_without(string("*/")) * string("*/")),
    ]

    keywords = [
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "int", "long", "register", "restrict", "return", "short", "signed",
        "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned",
        "void", "volatile", "while", "_Alignas", "_Alignof", "_Atomic",
        "_Bool", "_Complex", "_Generic", "_Imaginary", "_Noreturn",
        "_Static_assert", "_Thread_local", "__func__"
    ]

    for keyword in keywords:
        tokens.append((keyword, string(keyword)))

    tokens.append(("ident", L * A.star()))
    tokens.append(("hexconst", HP * H.plus() * IS.opt()))
    tokens.append(("octconst",  Char("0") * O.star() * IS.opt()))
    tokens.append(("intconst",  NZ * D.star() * IS.opt()))

    tokens.append(("charconst",
                   CP.opt() * Char("'") *
                   (ES | (AnyChar() & (~CharSet("'\\\n")))).plus() *
                   Char("'")))

    tokens.append(("floatconst",
                   D.plus() * E * FS.opt() |
                   D.star() * Char(".") * D.plus() * E.opt() * FS.opt() |
                   D.plus() * Char(".") * D.star() * E.opt() * FS.opt() |
                   HP * H.plus() * P * FS.opt() |
                   HP * H.star() * Char(".") * H.plus() * P * FS.opt() |
                   HP * H.plus() * Char(".") * P * FS.opt()))

    tokens.append(("string",
                   (SP.opt() * Char("\"") *
                    (ES | (AnyChar() & (~CharSet("\"\\\n")))).star() *
                    Char("\"") * WS.star()).plus()))

    ops = [
        ("ellipsis", "..."), ("rightassign", ">>="), ("leftassign", "<<="),
        ("addasign", "+="), ("subassign", "-="), ("mulassign", "*="),
        ("divassign", "/="), ("modassign", "%="), ("andassign", "&="),
        ("xorassign", "^="), ("orassign", "|="), ("rightop", ">>"),
        ("leftop", "<<"), ("incop", "++"), ("decop", "--"), ("ptrop", "->"),
        ("andop", "&&"), ("orop", "||"), ("leop", "<="), ("geop", ">="),
        ("eqop", "=="), ("neop", "!="), ("semicolon", ";"), ("lbrace", "{"),
        ("lbrace", "<%"), ("rbrace", "}"), ("rbrace", "%>"), ("comma", ","),
        ("colon", ":"), ("assign", "="), ("lparen", "("), ("rparen", ")"),
        ("lbracket", "["), ("lbracket", "<:"), ("rbracket", "]"),
        ("rbracket", ":>"), ("dot", "."), ("bitandop", "&"), ("notop", "!"),
        ("bitnotop", "~"), ("subop", "-"), ("addop", "+"), ("mulop", "*"),
        ("divop", "/"), ("modop", "%"), ("ltop", "<"), ("gtop", ">"),
        ("bitxorop", "^"), ("bitorop", "|"), ("ternaryop", "?"),
    ]

    for name, op in ops:
        tokens.append((name, string(op)))

    tokens.append(("space", WS.plus()))
    tokens.append(("bad", AnyChar()))

    return tokens


@pytest.fixture
def c_lexer(c_tokens):
    return make_lexer(c_tokens)


def c_lex(c_lexer, string):
    for tags, value in lex_all(c_lexer, string):
        if "space" not in tags:
            yield tags, value


TEST_SOURCE = """
size_t strlen(const char *s)
{
    size_t i;
    for (i = 0; s[i] != '\0'; i++);
    return i;
}
"""

TEST_TOKENS = [
# size_t strlen(const char *s)
    ({'ident'}, 'size_t'),
    ({'ident'}, 'strlen'),
    ({'lparen'}, '('),
    ({'const'}, 'const'),
    ({'char'}, 'char'),
    ({'mulop'}, '*'),
    ({'ident'}, 's'),
    ({'rparen'}, ')'),
# {
    ({'lbrace'}, '{'),
# size_t i;
    ({'ident'}, 'size_t'),
    ({'ident'}, 'i'),
    ({'semicolon'}, ';'),
# for (i = 0; s[i] != '\0'; i++) ;
    ({'for'}, 'for'),
    ({'lparen'}, '('),
    ({'ident'}, 'i'),
    ({'assign'}, '='),
    ({'octconst'}, '0'),
    ({'semicolon'}, ';'),
    ({'ident'}, 's'),
    ({'lbracket'}, '['),
    ({'ident'}, 'i'),
    ({'rbracket'}, ']'),
    ({'neop'}, '!='),
    ({'charconst'}, "'\x00'"),
    ({'semicolon'}, ';'),
    ({'ident'}, 'i'),
    ({'incop'}, '++'),
    ({'rparen'}, ')'),
    ({'semicolon'}, ';'),
# return i;
    ({'return'}, 'return'),
    ({'ident'}, 'i'),
    ({'semicolon'}, ';'),
# }
    ({'rbrace'}, '}'),
]


def test_lexer(c_lexer):
    assert list(c_lex(c_lexer, TEST_SOURCE)) == TEST_TOKENS
