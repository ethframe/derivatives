#include <stdio.h>

#include "matcher.h"


int test(const char *s) {
    struct DfaMatch match;

    dfa_match(s, &match);
    return (match.token == DFA_T_RE && *match.end == '\0') ? 1 : 0;
}


#define TEST(s) printf(s ": %d\n", test(s))


int main() {
    TEST("abba");
    TEST("aba");
    TEST("abbaa");
    return 0;
}
