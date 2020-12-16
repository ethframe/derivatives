from derivatives import (
    any_with, any_without, char, generate_c, generate_dot, make_lexer
)


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
        fp.write(generate_dot(lex))

    with open("matcher.h", "w") as fp:
        fp.write(generate_c(lex))


if __name__ == "__main__":
    main()
