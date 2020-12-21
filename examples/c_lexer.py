from typing import List, Tuple

from derivatives import (
    Regex, any_char, any_without, char, char_range, char_set, generate_c,
    generate_dot, make_lexer, select_first, string
)


def tokens() -> List[Tuple[str, Regex]]:
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
        ("comment", string("//") * (any_char() & (~char("\n"))).star()),
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
    tokens.append(("octconst", char("0") * O.star() * IS.opt()))
    tokens.append(("intconst", NZ * D.star() * IS.opt()))

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

    return tokens


def main() -> None:
    lex = make_lexer(tokens(), select_first)

    with open("c_lexer.dot", "w") as fp:
        fp.write(generate_dot(lex))

    with open("c_lexer.h", "w") as fp:
        fp.write(generate_c(lex))


if __name__ == "__main__":
    main()
