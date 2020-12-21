#include <stdio.h>

#include "matcher.h"


int test(const char *s) {
    struct DfaMatch match;

    if (dfa_match(s, &match) == DFA_END) {
        return (match.end != NULL && *match.end == '\0') ? 1 : 0;
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
