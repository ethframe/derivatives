from derivatives import *


def string(s):
    regex = Epsilon()
    for c in s:
        regex *= Char(c)
    return regex


def anywhere(regex):
    return AnyChar().star() * regex * AnyChar().star()


def no(regex):
    return ~anywhere(regex)


def make_lexer(tokens):
    regex = Empty()
    parts = Empty()
    for name, tok in tokens:
        regex |= (tok - parts).dfa() * Tag(name)
        parts = (parts | tok).dfa()
    return regex.dfa()


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


def main():
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
        ("comment", string("/*") * no(string("*/")) * string("*/")),
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

    lexer = make_lexer(tokens)

    source = """
int yywrap(void)        /* called at end of input */
{
    return 1;           /* terminate now */
}

static void comment(void)
{
    int c;

    while ((c = input()) != 0)
        if (c == '*')
        {
            while ((c = input()) == '*')
                ;

            if (c == '/')
                return;

            if (c == 0)
                break;
        }
    yyerror("unterminated comment");
}

static int check_type(void)
{
    switch (sym_type(yytext))
    {
    case TYPEDEF_NAME:                /* previously defined */
        return TYPEDEF_NAME;
    case ENUMERATION_CONSTANT:        /* previously defined */
        return ENUMERATION_CONSTANT;
    default:                          /* includes undefined */
        return IDENTIFIER;
    }
}"""
    while source:
        pos, tag = lex_once(lexer, source)
        if "space" not in tag:
            print(tag, repr(source[:pos]))
        source = source[pos:]

    word = CharRange("a", "z").plus()
    num = CharRange("0", "9").plus()

    re_a = (word * Char(" ")).opt() * string("test")
    re_b = (num * Char(" ")).opt() * string("test")
    re_c = string("test test")
    re_d = (num * word * Char(" ")) * string("test")
    comm = (re_a * Tag("A") | re_b * Tag("B") |
            re_c * Tag("C") | re_d * Tag("D"))
    print(comm.dfa().conflicts())


if __name__ == '__main__':
    main()
