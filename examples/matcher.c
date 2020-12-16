#include <stdio.h>

#include "matcher.h"


int test(const char *s) {
    struct Dfa dfa;

    dfa_reset(&dfa);

    for (; *s; ++s) {
        switch (dfa_handle(&dfa, *s)) {
        case DFA_END:
        case DFA_END_MATCH:
        case DFA_ERROR:
            return 0;
        }
    }

    switch (dfa_handle_eof(&dfa)) {
    case DFA_END_MATCH:
        return (dfa.token == DFA_T_RE) ? 1 : 0;
    }
    return 0;
}


#define TEST(s) printf(s ": %d\n", test(s))


int main() {
    TEST("abba");
    TEST("aba");
    TEST("abbaa");
    return 0;
}
