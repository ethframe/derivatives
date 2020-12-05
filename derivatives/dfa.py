import html
from collections import defaultdict, deque
from contextlib import contextmanager
from io import StringIO
from itertools import count
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from .core import Regex

DfaTransition = Tuple[str, str, int]
DfaTransitions = List[DfaTransition]
DfaDelta = List[DfaTransitions]
DfaTags = List[Optional[str]]


class DfaRunner:
    def __init__(self, delta: DfaDelta, tags: DfaTags):
        self._state = 0
        self._delta = delta
        self._tags = tags

    def handle(self, char: str) -> bool:
        for start, end, target in self._delta[self._state]:
            if start <= char <= end:
                self._state = target
                return True
            if char < start:
                break
        return False

    def tag(self) -> Optional[str]:
        return self._tags[self._state]


class Dfa:
    def __init__(self, delta: DfaDelta, tags: DfaTags):
        self._delta = delta
        self._tags = tags

    def start(self) -> DfaRunner:
        return DfaRunner(self._delta, self._tags)

    def scan_once(self, input: str) -> Optional[Tuple[str, int]]:
        result: Optional[Tuple[str, int]] = None
        runner = self.start()
        tag = runner.tag()
        if tag:
            result = (tag, 0)
        for pos, char in enumerate(input, 1):
            if not runner.handle(char):
                break
            tag = runner.tag()
            if tag:
                result = (tag, pos)
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
        def fmt_char(char: str) -> str:
            if char in "\\-[]":
                return "\\" + char
            return html.escape(char).encode("unicode_escape").decode("ascii")

        buf = Buffer(2)
        buf.line("digraph dfa {")
        with buf.indent():
            buf.line("rankdir=LR")
            buf.line('"" [shape=none]')
            buf.line('"" -> "0"')

            seen_tags: Set[str] = set()
            for state, tag in enumerate(self._tags):
                shape = "circle"
                if tag is not None:
                    shape = "doublecircle"
                    seen_tags.add(tag)
                buf.format('"{}" [shape={} fixedsize=shape]', state, shape)

            for tag in sorted(seen_tags):
                buf.format(
                    '"t_{0}" [shape=rect style=dashed label="{0}"]', tag
                )

            for state, trantisions in enumerate(self._delta):
                compact: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
                for start, end, target in trantisions:
                    compact[target].append((start, end))
                for target, ranges in compact.items():
                    classes = []
                    for start, end in ranges:
                        size = ord(end) - ord(start) + 1
                        if size == 1:
                            classes.append(fmt_char(start))
                        elif size <= 3:
                            classes.append(
                                "".join(
                                    fmt_char(chr(c))
                                    for c in range(ord(start), ord(end) + 1)
                                )
                            )
                        else:
                            classes.append(
                                fmt_char(start) + "-" + fmt_char(end)
                            )
                    label = "[{}]".format("".join(classes))
                    buf.format(
                        '"{}" -> "{}" [label=<{}>]', state, target, label
                    )
                tag = self._tags[state]
                if tag is not None:
                    buf.format('"{}" -> "t_{}" [style=dashed]', state, tag)

        buf.line("}")
        return buf.getvalue()

    def to_c(self) -> str:
        buf = Buffer(4)
        buf.line("#include <stdint.h>")
        buf.skip()
        buf.line("#define DFA_NEED_INPUT -1")
        buf.line("#define DFA_ERROR -2")
        buf.skip()
        buf.line("struct Dfa {")
        with buf.indent():
            buf.line("unsigned int state;")
        buf.line("};")
        buf.skip()
        buf.line(
            "static inline void dfa_reset(struct Dfa *dfa) { dfa->state = 0; }"
        )
        buf.skip()
        tokens = sorted({tag for tag in self._tags if tag is not None})
        for value, name in enumerate(tokens):
            buf.format("#define T_{} {}", name.upper(), value)
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
                    last_end = 0
                    for start, end, target in transitions:
                        err = ord(start)
                        if last_end < err:
                            buf.format(
                                "if (c < {}) {{ return DFA_ERROR; }}", err
                            )
                        tag = self._tags[target]
                        if tag is None:
                            ret = "DFA_NEED_INPUT"
                        else:
                            ret = "T_{}".format(tag.upper())
                        last_end = ord(end) + 1
                        buf.format(
                            "if (c < {}) {{ dfa->state = {}; return {}; }}",
                            last_end, target, ret
                        )
                    buf.line("break;")
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


def make_dfa(regex: Regex, tag_resolver: Callable[[Set[int]], str]) -> Dfa:
    delta: Dict[int, DfaTransitions] = {}
    tags: Dict[int, str] = {}

    incoming: Dict[int, Set[int]] = defaultdict(set)

    state_map: Dict[Regex, int] = defaultdict(count().__next__)
    queue = deque([(state_map[regex], regex)])

    while queue:
        state, regex = queue.popleft()
        state_delta = delta[state] = []
        state_tags = regex.tags()
        if state_tags:
            tags[state] = tag_resolver(state_tags)

        last = 0
        for end, target in regex.derivatives():
            len_before = len(state_map)
            target_state = state_map[target]
            incoming[target_state].add(state)
            if len(state_map) != len_before:
                queue.append((target_state, target))
            state_delta.append((chr(last), chr(end - 1), target_state))
            last = end

    live = set(tags)
    live_queue = deque(tags)
    while live_queue:
        state = live_queue.popleft()
        for source_state in incoming[state]:
            if source_state not in live:
                live.add(source_state)
                live_queue.append(source_state)

    new_to_old = sorted(live)
    old_to_new = dict((state, i) for i, state in enumerate(new_to_old))

    return Dfa(
        [
            [
                (start, end, old_to_new[target])
                for start, end, target in delta[old_state]
                if target in old_to_new
            ]
            for old_state in new_to_old
        ],
        [tags.get(old_state) for old_state in new_to_old],
    )
