from derivatives import char, any_with, any_without, make_lexer


def main() -> None:
    lex = make_lexer([
        (
            "re",
            (
                (char("a") | char("b")).plus() &
                any_without(char("a") * char("a")) &
                any_with(char("b") * char("b"))
            )
        )
    ])
    with open("matcher.dot", "w") as fp:
        fp.write(lex.to_dot())

    with open("matcher.h", "w") as fp:
        fp.write(lex.to_c())


if __name__ == "__main__":
    main()
