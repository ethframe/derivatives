import pytest

from derivatives import (
    any_char, any_without, char, char_range, char_set, lex_all, make_lexer,
    string
)


@pytest.fixture
def c_tokens():
    # Adapted from http://www.quut.com/c/ANSI-C-grammar-l.html
    O = char_range("0", "7")
    D = char_range("0", "9")
    NZ = char_range("1", "9")
    L = char_range("a", "z") | char_range("A", "Z") | char("_")
    A = L | D
    H = char_range("a", "f") | char_range("A", "F") | D
    HP = char("0") * char_set("xX")
    E = char_set("Ee") * char_set("+-").opt() * D.plus()
    P = char_set("Pp") * char_set("+-").opt() * D.plus()
    FS = char_set("fFlL")
    IS = char_set("uU") * (char_set("lL") | string("ll") |
                          string("LL")).opt() | \
        (char_set("lL") | string("ll") | string("LL")) * char_set("uU").opt()
    CP = char_set("uUL")
    SP = string("u8") | CP
    ES = char("\\") * (char_set("'\"?\\abfnrtv") | O | O * O | O * O * O |
                       char("x") * H.plus())
    WS = char_set(" \t\v\n\f")

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
    tokens.append(("octconst",  char("0") * O.star() * IS.opt()))
    tokens.append(("intconst",  NZ * D.star() * IS.opt()))

    tokens.append(("charconst",
                   CP.opt() * char("'") *
                   (ES | (any_char() & (~char_set("'\\\n")))).plus() *
                   char("'")))

    tokens.append(("floatconst",
                   D.plus() * E * FS.opt() |
                   D.star() * char(".") * D.plus() * E.opt() * FS.opt() |
                   D.plus() * char(".") * D.star() * E.opt() * FS.opt() |
                   HP * H.plus() * P * FS.opt() |
                   HP * H.star() * char(".") * H.plus() * P * FS.opt() |
                   HP * H.plus() * char(".") * P * FS.opt()))

    tokens.append(("string",
                   (SP.opt() * char("\"") *
                    (ES | (any_char() & (~char_set("\"\\\n")))).star() *
                    char("\"") * WS.star()).plus()))

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
    tokens.append(("bad", any_char()))

    return tokens


@pytest.fixture
def c_lexer(c_tokens):
    return make_lexer(c_tokens)


def c_lex(c_lexer, string):
    for tags, value in lex_all(c_lexer, string):
        tag = tags[0]
        if tag != "space":
            yield tag, value


TEST_SOURCE = """
size_t strlen(const char *s)
{
    /** Simple strlen function **/
    size_t i;
    for (i = 0; s[i] != '\0'; i++);
    return i;
}
"""

TEST_TOKENS = [
    # size_t strlen(const char *s)
    ('ident', 'size_t'),
    ('ident', 'strlen'),
    ('lparen', '('),
    ('const', 'const'),
    ('char', 'char'),
    ('mulop', '*'),
    ('ident', 's'),
    ('rparen', ')'),
    # {
    ('lbrace', '{'),
    # /** Simple strlen function **/
    ('comment', '/** Simple strlen function **/'),
    # size_t i;
    ('ident', 'size_t'),
    ('ident', 'i'),
    ('semicolon', ';'),
    # for (i = 0; s[i] != '\0'; i++) ;
    ('for', 'for'),
    ('lparen', '('),
    ('ident', 'i'),
    ('assign', '='),
    ('octconst', '0'),
    ('semicolon', ';'),
    ('ident', 's'),
    ('lbracket', '['),
    ('ident', 'i'),
    ('rbracket', ']'),
    ('neop', '!='),
    ('charconst', "'\x00'"),
    ('semicolon', ';'),
    ('ident', 'i'),
    ('incop', '++'),
    ('rparen', ')'),
    ('semicolon', ';'),
    # return i;
    ('return', 'return'),
    ('ident', 'i'),
    ('semicolon', ';'),
    # }
    ('rbrace', '}'),
]


def test_lexer(c_lexer):
    assert list(c_lex(c_lexer, TEST_SOURCE)) == TEST_TOKENS
