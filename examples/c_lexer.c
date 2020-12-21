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
        switch (dfa_match(s, &match)) {
        case DFA_END:
            if (match.end == NULL) { return -1; }
            if (match.token != DFA_T_SPACE) {
                print_token(match.token, match.begin, match.end);
            }
            s = match.end;
            break;
        case DFA_ERROR:
            return -1;
        }
    }
}


int main() {
    return lex("int main() { int r = foo(1, \"a\"); if (r == 1) { bar(); } return 0; }");
}
