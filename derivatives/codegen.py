import html
from collections import defaultdict
from contextlib import contextmanager
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .dfa import Dfa, DfaTransitions
from .partition import CHARSET_END


class Buffer:
    def __init__(self, indent: int = 2):
        self._buffer = StringIO()
        self._indent = " " * indent
        self._level = 0

    @contextmanager
    def indent(self) -> Iterator[None]:
        self._level += 1
        yield
        self._level -= 1

    def skip(self, n: int = 1) -> None:
        self._buffer.write("\n" * n)

    def line(self, s: str, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            s = s.format(*args, **kwargs)
        self._buffer.write(self._indent * self._level)
        self._buffer.write(s)
        self._buffer.write("\n")

    def unindented(self, s: str, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            s = s.format(*args, **kwargs)
        self._buffer.write(s)
        self._buffer.write("\n")

    def getvalue(self) -> str:
        return self._buffer.getvalue()


def fmt_char(code: int) -> str:
    char = chr(code)
    if char in "\\-[]":
        return "\\" + char
    return html.escape(char).encode("unicode_escape").decode("ascii")


def generate_dot(dfa: Dfa) -> str:
    buf = Buffer(2)
    buf.line("digraph dfa {")
    with buf.indent():
        buf.line("rankdir=LR")
        buf.line('"" [shape=none]')
        buf.line('"" -> "0"')
        buf.line('"end" [shape=doublecircle]')

        for state, tag in dfa.iter_eof_tags():
            buf.line('"{}" [shape=circle fixedsize=shape]', state)
            if tag:
                buf.line('"{}" -> "end" [label="EOF/{}"]', state, tag)

        for state, trantisions in dfa.iter_delta():
            grouped: Dict[
                Tuple[Optional[int], Optional[str]],
                List[Tuple[int, int]]
            ] = defaultdict(list)
            last = 0
            for end, target, tag in trantisions:
                grouped[(target, tag)].append((last, end - 1))
                last = end
            for (target, tag), ranges in grouped.items():
                classes = []
                for start, end in ranges:
                    size = end - start + 1
                    if size == 1:
                        classes.append(fmt_char(start))
                    elif size <= 3:
                        classes.append(
                            "".join(fmt_char(c) for c in range(start, end + 1))
                        )
                    else:
                        classes.append(fmt_char(start) + "-" + fmt_char(end))
                label = "[{}]".format("".join(classes))
                if tag is not None:
                    label += "/" + tag
                if target is not None:
                    buf.line('"{}" -> "{}" [label=<{}>]', state, target, label)

    buf.line("}")
    return buf.getvalue()


def c_token_name(tag: str) -> str:
    return "DFA_T_" + tag.upper()


def generate_c(dfa: Dfa) -> str:
    buf = Buffer(4)

    buf.line("#ifndef DERIVATIVES_DFA_H")
    buf.line("#define DERIVATIVES_DFA_H")
    buf.skip()

    buf.line("#include <stdint.h>")
    buf.skip()

    generate_c_tokens(buf, dfa)
    buf.skip()

    buf.line("struct DfaMatch {")
    with buf.indent():
        buf.line("const char *begin;")
        buf.line("const char *end;")
        buf.line("unsigned int token;")
    buf.line("};")
    buf.skip()

    generate_c_match(buf, dfa)
    buf.skip()

    buf.line("#endif /* DERIVATIVES_DFA_H */")
    return buf.getvalue()


def generate_c_tokens(buf: Buffer, dfa: Dfa) -> None:
    tokens = sorted(dfa.get_tags_set())

    buf.line("#define DFA_INVALID_TOKEN 0")
    for value, tag in enumerate(tokens, 1):
        buf.line("#define {} {}", c_token_name(tag), value)
    buf.skip()

    buf.line("static const char *dfa_token_name(int t) {")
    with buf.indent():
        buf.line("static const char *table[] = {")
        with buf.indent():
            for name in tokens:
                buf.line('"{}",', name)
        buf.line("};")
        buf.line("if (t < 0 || t >= {}) {{ return NULL; }}", len(tokens))
        buf.line("return table[t];")
    buf.line("};")


def generate_c_match(buf: Buffer, dfa: Dfa) -> None:
    buf.line(
        "static inline void dfa_match(const char *s, struct DfaMatch *match) {"
    )
    with buf.indent():
        buf.line("unsigned char c;")
        buf.skip()
        buf.line("match->begin = match->end = s;")
        buf.line("match->token = DFA_INVALID_TOKEN;")
        buf.skip()
        for state, transitions in dfa.iter_delta():
            buf.unindented("S{}:", state)
            buf.line("c = *(s++);")
            for end, target, tag in transitions:
                action = c_transition_action(target, tag)
                if end == CHARSET_END:
                    buf.line(action)
                else:
                    buf.line("if (c < {}) {{ {} }}", end, action)
    buf.line("}")


def c_transition_action(target: Optional[int], tag: Optional[str]) -> str:
    action: List[str] = []
    if tag is not None:
        action.extend([
            "match->end = s - 1;",
            "match->token = {};".format(c_token_name(tag))
        ])
    if target is None:
        action.append("return;")
    else:
        action.append("goto S{};".format(target))
    return " ".join(action)
