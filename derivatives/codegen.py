import html
from collections import defaultdict
from contextlib import contextmanager
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .dfa import Dfa, DfaState, DfaTransition, DfaTransitions
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

        for state, data in dfa.iter_states():
            label = str(state)
            if data.entry_tag:
                label += "/" + data.entry_tag
            buf.line(
                '"{}" [shape=circle fixedsize=shape label=<{}>]', state, label
            )
            if data.eof_tag:
                buf.line('"{}" -> "end" [label="EOF/{}"]', state, data.eof_tag)

        for state, data in dfa.iter_states():
            grouped: Dict[
                Tuple[Optional[int], Optional[str]],
                List[Tuple[int, int]]
            ] = defaultdict(list)
            last = 0
            for end, target, tag in data.transitions:
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
                elif tag is not None:
                    buf.line('"{}" -> "end" [label=<{}>]', state, label)

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
    tokens = dfa.get_tags()

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
        buf.line("if (t <= 0 || t > {}) {{ return NULL; }}", len(tokens))
        buf.line("return table[t - 1];")
    buf.line("};")


def generate_c_match(buf: Buffer, dfa: Dfa) -> None:
    buf.unindented("#ifdef DFA_USE_LIMIT")
    buf.line(
        "static inline void dfa_match(const char *s, const char *limit,"
        " struct DfaMatch *match) {"
    )
    buf.unindented("#else")
    buf.line(
        "static inline void dfa_match(const char *s, struct DfaMatch *match) {"
    )
    buf.unindented("#endif")
    with buf.indent():
        buf.line("unsigned char c;")
        buf.skip()
        buf.line("match->begin = match->end = s;")
        buf.line("match->token = DFA_INVALID_TOKEN;")
        buf.skip()
        for state, data in dfa.iter_states():
            buf.unindented("S{}:", state)
            if data.entry_tag is not None:
                buf.line(c_tag_action(data.entry_tag, True))
            first, *rest = data.transitions
            generate_c_eof_transition(buf, first, data)
            generate_c_transitions(buf, rest)
    buf.line("}")


def generate_c_eof_transition(
        buf: Buffer, first: DfaTransition, data: DfaState) -> None:
    end, target, tag = first
    first_transition = c_transition_condition(end, target, tag, False)
    handles_null = target is None and tag == data.eof_tag
    buf.unindented("#ifdef DFA_USE_LIMIT")
    buf.line(
        "if (s == limit) {{ {} }}", c_transition(None, data.eof_tag, True)
    )
    if not handles_null:
        buf.line("c = *(s++);")
        if end == 1:
            buf.line(first_transition)
        buf.unindented("#else")
        buf.line("c = *(s++);")
        buf.line(
            "if (c == 0) {{ {} }}", c_transition(None, data.eof_tag, False)
        )
    buf.unindented("#endif")
    if handles_null:
        buf.line("c = *(s++);")
        buf.line(first_transition)


def generate_c_transitions(buf: Buffer, transitions: DfaTransitions) -> None:
    for end, target, tag in transitions:
        buf.line(c_transition_condition(end, target, tag, False))


def c_transition_condition(
        end: int, target: Optional[int], tag: Optional[str],
        entry: bool) -> str:
    transition = c_transition(target, tag, entry)
    if end == CHARSET_END:
        return transition
    return "if (c < {}) {{ {} }}".format(end, transition)


def c_tag_action(tag: str, entry: bool) -> str:
    pos = "s" if entry else "s - 1"
    return "match->end = {}; match->token = {};".format(pos, c_token_name(tag))


def c_transition(
        target: Optional[int], tag: Optional[str], entry: bool) -> str:
    transition = "return;" if target is None else "goto S{};".format(target)
    if tag is not None:
        transition = "{} {}".format(c_tag_action(tag, entry), transition)
    return transition
