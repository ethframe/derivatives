import html
from collections import defaultdict
from contextlib import contextmanager
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .dfa import Dfa, DfaTransition


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

    def line(self, s: str) -> None:
        self._buffer.write(self._indent * self._level)
        self._buffer.write(s)
        self._buffer.write("\n")

    def format(self, s: str, *args: Any, **kwargs: Any) -> None:
        self.line(s.format(*args, **kwargs))

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
            buf.format('"{}" [shape=circle fixedsize=shape]', state)
            if tag:
                buf.format('"{}" -> "end" [label="EOF/{}"]', state, tag)

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
                    buf.format(
                        '"{}" -> "{}" [label=<{}>]', state, target, label
                    )

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

    buf.line("#define DFA_ERROR -1")
    buf.line("#define DFA_CONTINUE 0")
    buf.line("#define DFA_MATCH 1")
    buf.line("#define DFA_END 2")
    buf.line("#define DFA_END_MATCH 3")
    buf.skip()

    generate_c_tokens(buf, dfa)
    buf.skip()

    buf.line("struct Dfa {")
    with buf.indent():
        buf.line("unsigned int state;")
        buf.line("unsigned int token;")
    buf.line("};")
    buf.skip()
    buf.line("static inline void dfa_reset(struct Dfa *dfa) {")
    with buf.indent():
        buf.line("dfa->state = 0;")
    buf.line("}")
    buf.skip()

    generate_c_handle(buf, dfa)
    buf.skip()
    generate_c_handle_eof(buf, dfa)
    buf.skip()

    buf.line("#endif /* DERIVATIVES_DFA_H */")
    return buf.getvalue()


def generate_c_tokens(buf: Buffer, dfa: Dfa) -> None:
    tokens = sorted(dfa.get_tags_set())

    for value, tag in enumerate(tokens):
        buf.format("#define {} {}", c_token_name(tag), value)
    buf.skip()

    buf.line("static const char *dfa_token_name(int t) {")
    with buf.indent():
        buf.line("static const char *table[] = {")
        with buf.indent():
            for name in tokens:
                buf.format('"{}",', name)
        buf.line("};")
        buf.format("if (t < 0 || t >= {}) {{ return NULL; }}", len(tokens))
        buf.format("return table[t];")
    buf.line("};")


def generate_c_handle(buf: Buffer, dfa: Dfa) -> None:
    buf.line("static inline int dfa_handle(struct Dfa *dfa, uint32_t c) {")
    with buf.indent():
        buf.line("switch (dfa->state) {")
        for state, transitions in dfa.iter_delta():
            buf.format("case {}:", state)
            with buf.indent():
                generate_c_transitions(buf, transitions)
                buf.line("break;")
        buf.line("}")
        buf.line("return DFA_ERROR;")
    buf.line("}")


def generate_c_transitions(
        buf: Buffer, transitions: List[DfaTransition]) -> None:
    for end, target, tag in transitions:
        if tag is None:
            if target is None:
                buf.format("if (c < {}) {{ return DFA_END; }}", end)
            else:
                buf.format(
                    "if (c < {}) {{ dfa->state = {}; return DFA_CONTINUE; }}",
                    end, target
                )
        else:
            if target is None:
                buf.format(
                    "if (c < {}) {{ dfa->token = {}; return DFA_END_MATCH; }}",
                    end, c_token_name(tag)
                )
            else:
                buf.format(
                    "if (c < {}) {{ dfa->token = {};"
                    " dfa->state = {}; return DFA_MATCH; }}",
                    end, c_token_name(tag), target
                )


def generate_c_handle_eof(buf: Buffer, dfa: Dfa) -> None:
    buf.line("static inline int dfa_handle_eof(struct Dfa *dfa) {")
    with buf.indent():
        buf.line("switch (dfa->state) {")
        for state, tag in dfa.iter_eof_tags():
            if tag is None:
                continue
            buf.format("case {}:", state)
            with buf.indent():
                buf.format("dfa->token = {};", c_token_name(tag))
                buf.format("return DFA_END_MATCH;")
        buf.line("default:")
        with buf.indent():
            buf.format("return DFA_END;")
        buf.line("}")
        buf.line("return DFA_ERROR;")
    buf.line("}")
