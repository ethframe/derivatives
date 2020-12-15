import html
from collections import defaultdict, deque
from contextlib import contextmanager
from io import StringIO
from itertools import count
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from .vector import Vector

DfaTransition = Tuple[int, Optional[int], Optional[str]]
DfaTransitions = List[DfaTransition]
DfaDelta = List[DfaTransitions]
DfaTags = List[Optional[str]]


class DfaRunner:
    def __init__(self, delta: DfaDelta, eof_tags: DfaTags):
        self._state: Optional[int] = 0
        self._delta = delta
        self._eof_tags = eof_tags
        self._tag: Optional[str] = None

    def handle(self, char: str) -> bool:
        state = self._state
        if state is None:
            return False
        code = ord(char)
        for end, target, tag in self._delta[state]:
            if code < end:
                self._state = target
                self._tag = tag
                return True
        return False

    def handle_eof(self) -> bool:
        state = self._state
        if state is None:
            return False
        self._tag = self._eof_tags[state]
        return True

    def tag(self) -> Optional[str]:
        return self._tag


class Dfa:
    def __init__(self, delta: DfaDelta, eof_tags: DfaTags):
        self._delta = delta
        self._eof_tags = eof_tags

    def start(self) -> DfaRunner:
        return DfaRunner(self._delta, self._eof_tags)

    def scan_once(self, input: str) -> Optional[Tuple[str, int]]:
        result: Optional[Tuple[str, int]] = None
        runner = self.start()
        tag = runner.tag()
        if tag:
            result = (tag, 0)
        for pos, char in enumerate(input):
            if not runner.handle(char):
                break
            tag = runner.tag()
            if tag:
                result = (tag, pos)
        if runner.handle_eof():
            tag = runner.tag()
            if tag:
                result = (tag, len(input))
        return result

    def scan_all(self, input: str) -> Iterator[Tuple[str, str]]:
        while input:
            result = self.scan_once(input)
            if result is None:
                raise ValueError("Input not recognized")
            tag, pos = result
            yield tag, input[:pos]
            input = input[pos:]

    def to_dot(self) -> str:
        def fmt_char(code: int) -> str:
            char = chr(code)
            if char in "\\-[]":
                return "\\" + char
            return html.escape(char).encode("unicode_escape").decode("ascii")

        buf = Buffer(2)
        buf.line("digraph dfa {")
        with buf.indent():
            buf.line("rankdir=LR")
            buf.line('"" [shape=none]')
            buf.line('"" -> "0"')
            buf.line('"end" [shape=doublecircle]')

            for state, tag in enumerate(self._eof_tags):
                buf.format('"{}" [shape=circle fixedsize=shape]', state)
                if tag:
                    buf.format('"{}" -> "end" [label="EOF/{}"]', state, tag)

            for state, trantisions in enumerate(self._delta):
                compact: Dict[
                    Tuple[Optional[int], Optional[str]],
                    List[Tuple[int, int]]
                ] = defaultdict(list)
                last = 0
                for end, target, tag in trantisions:
                    compact[(target, tag)].append((last, end - 1))
                    last = end
                for (target, tag), ranges in compact.items():
                    classes = []
                    for start, end in ranges:
                        size = end - start + 1
                        if size == 1:
                            classes.append(fmt_char(start))
                        elif size <= 3:
                            classes.append(
                                "".join(
                                    fmt_char(c)
                                    for c in range(start, end + 1)
                                )
                            )
                        else:
                            classes.append(
                                fmt_char(start) + "-" + fmt_char(end)
                            )
                    label = "[{}]".format("".join(classes))
                    if tag is not None:
                        label += "/" + tag
                    if target is not None:
                        buf.format(
                            '"{}" -> "{}" [label=<{}>]', state, target, label
                        )

        buf.line("}")
        return buf.getvalue()

    def to_c(self) -> str:
        buf = Buffer(4)
        buf.line("#include <stdint.h>")
        buf.skip()
        buf.line("#define DFA_ERROR -1")
        buf.line("#define DFA_CONTINUE 0")
        buf.line("#define DFA_MATCH 1")
        buf.line("#define DFA_END 2")
        buf.line("#define DFA_END_MATCH 3")
        buf.skip()
        tags = {tag for tag in self._eof_tags if tag is not None}
        for transitions in self._delta:
            for _, _, tag in transitions:
                if tag is not None:
                    tags.add(tag)

        def tag_macro(tag: str) -> str:
            return "DFA_T_" + tag.upper()

        tokens = sorted(tags)
        for value, tag in enumerate(tokens):
            buf.format("#define {} {}", tag_macro(tag), value)
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
        buf.skip()
        buf.line(
            "static inline int dfa_handle(struct Dfa *dfa, uint32_t c) {"
        )
        with buf.indent():
            buf.line("switch (dfa->state) {")
            for state, transitions in enumerate(self._delta):
                buf.format("case {}:", state)
                with buf.indent():
                    for end, target, tag in transitions:
                        if tag is None:
                            if target is None:
                                buf.format(
                                    "if (c < {}) {{ return DFA_END; }}", end
                                )
                            else:
                                buf.format(
                                    "if (c < {}) {{ dfa->state = {};"
                                    " return DFA_CONTINUE; }}",
                                    end, target
                                )
                        else:
                            if target is None:
                                buf.format(
                                    "if (c < {}) {{ dfa->token = {};"
                                    " return DFA_END_MATCH; }}",
                                    end, tag_macro(tag)
                                )
                            else:
                                buf.format(
                                    "if (c < {}) {{ dfa->token = {};"
                                    " dfa->state = {}; return DFA_MATCH; }}",
                                    end, tag_macro(tag), target
                                )
                    buf.line("break;")
            buf.line("}")
            buf.line("return DFA_ERROR;")
        buf.line("}")
        buf.skip()
        buf.line("static inline int dfa_handle_eof(struct Dfa *dfa) {")
        with buf.indent():
            buf.line("switch (dfa->state) {")
            for state, tag in enumerate(self._eof_tags):
                if tag is None:
                    continue
                buf.format("case {}:", state)
                with buf.indent():
                    buf.format("dfa->token = {};", tag_macro(tag))
                    buf.format("return DFA_END_MATCH;")
            buf.line("default:")
            with buf.indent():
                buf.format("return DFA_END;")
            buf.line("}")
            buf.line("return DFA_ERROR;")
        buf.line("}")
        buf.skip()
        return buf.getvalue()


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


def make_dfa(vector: Vector, tag_resolver: Callable[[Set[int]], str]) -> Dfa:
    delta: Dict[int, List[Tuple[int, int, Optional[str]]]] = {}
    eof_tags: Dict[int, str] = {}

    incoming: Dict[int, Set[int]] = defaultdict(set)

    state_map: Dict[Vector, int] = defaultdict(count().__next__)
    queue = deque([(state_map[vector], vector, vector.tags())])

    live: Set[int] = set()

    while queue:
        state, vector, state_tags = queue.popleft()
        state_delta = delta[state] = []
        if state_tags:
            eof_tags[state] = tag_resolver(state_tags)
            live.add(state)

        for end, target in vector.transitions():
            len_before = len(state_map)
            target_state = state_map[target]
            target_tags = target.tags()
            incoming[target_state].add(state)
            if len(state_map) != len_before:
                queue.append((target_state, target, target_tags))
            transition_tags = state_tags - target_tags
            if transition_tags:
                transition_tag: Optional[str] = tag_resolver(transition_tags)
            else:
                transition_tag = None
            state_delta.append((end, target_state, transition_tag))

    live_queue = deque(live)
    while live_queue:
        state = live_queue.popleft()
        for source_state in incoming[state]:
            if source_state not in live:
                live.add(source_state)
                live_queue.append(source_state)

    new_to_old = sorted(live)
    old_to_new = dict((state, i) for i, state in enumerate(new_to_old))

    pruned_delta = [
        [
            (end, old_to_new.get(target, None), tag)
            for end, target, tag in delta[old_state]
        ]
        for old_state in new_to_old
    ]
    pruned_eof_tags = [
        eof_tags.get(old_state, None) for old_state in new_to_old
    ]

    return Dfa(pruned_delta, pruned_eof_tags)
