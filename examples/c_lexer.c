#include <stdio.h>

#include "c_lexer.h"


void print_token(int token, const char *begin, const char *end) {
    printf("%s: [", dfa_token_name(token));
    for (; begin != end; ++begin) { putchar(*begin); }
    printf("]\n");
}


int lex(const char *s) {
    struct DfaMatch match;

    while (*s) {
        dfa_match(s, &match);
        if (match.token == DFA_INVALID_TOKEN) { return -1; }
        if (match.token != DFA_T_SPACE) {
            print_token(match.token, match.begin, match.end);
        }
        s = match.end;
    }
    return 0;
}


int main() {
    return lex("int main() { int r = foo(1, \"a\"); if (r == 1) { bar(); } return 0; } // \xd0\x90\n");
}
