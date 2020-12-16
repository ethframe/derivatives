#include <stdio.h>

#include "c_lexer.h"


void print_token(int token, const char *begin, const char *end) {
    printf("%s: [", dfa_token_name(token));
    for (; begin != end; ++begin) { putchar(*begin); }
    printf("]\n");
}


int lex(const char *s) {
    struct Dfa dfa;

    const char *begin = s;
    const char *end = NULL;
    int token;

    dfa_reset(&dfa);

    while (*s) {
        switch (dfa_handle(&dfa, *s)) {
        case DFA_MATCH:
            token = dfa.token;
            end = s;
        case DFA_CONTINUE:
            ++s;
            break;
        case DFA_END_MATCH:
            token = dfa.token;
            end = s;
        case DFA_END:
            if (end == NULL) { return -1; }
            if (token != DFA_T_SPACE) { print_token(token, begin, end); }
            s = begin = end;
            end = NULL;
            dfa_reset(&dfa);
            break;
        case DFA_ERROR:
            return -1;
        }
    }

    switch (dfa_handle_eof(&dfa)) {
    case DFA_END_MATCH:
        token = dfa.token;
        end = s;
    case DFA_END:
        if (end == NULL) { return -1; }
        if (token != DFA_T_SPACE) { print_token(token, begin, end); }
        return 0;
    }
    return -1;
}


int main() {
    return lex("int main() { int r = foo(1, \"a\"); if (r == 1) { bar(); } return 0; }");
}
