from collections import defaultdict, deque
from itertools import count
from typing import List, Set, Tuple

from .core import Empty, Regex


class Vector:
    def __init__(self, items: List[Tuple[str, Regex]]):
        self._items = items

    def alphabet(self) -> Set[str]:
        result: Set[str] = set()
        for _, regex in self._items:
            result |= regex.alphabet()
        return result

    def first(self) -> Set[str]:
        result: Set[str] = set()
        for _, regex in self._items:
            result |= regex.first()
        return result

    def derive(self, char: str) -> 'Vector':
        return Vector(
            [(tag, regex.derive(char)) for tag, regex in self._items])

    def tags(self) -> List[str]:
        return [tag for tag, regex in self._items if regex.nullable()]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return self._items == other._items

    def __hash__(self) -> int:
        return hash((Vector, tuple(self._items)))


def make_dfa(vector):
    state_map = defaultdict(count().__next__)
    start = state_map[vector]
    queue = deque([(state_map[vector], vector)])
    delta = {}
    tags = {}
    accepting = []
    alphabet = sorted(vector.alphabet())

    while queue:
        state_index, state = queue.popleft()
        delta[state_index] = {}
        state_tags = tags[state_index] = state.tags()
        if state_tags:
            accepting.append(state_index)
        for char in state.first():
            next_state = state.derive(char)
            if isinstance(next_state, Empty):
                continue
            sm_len = len(state_map)
            next_index = state_map[next_state]
            if sm_len != len(state_map):
                queue.append((next_index, next_state))
            delta[state_index][char] = next_index

    return start, delta, accepting, alphabet, tags


def inplace_refine(target, refiner):
    common = target & refiner
    if not common:
        return
    if len(common) * 2 < len(target):
        target.difference_update(refiner)
        return common
    distinct = target - common
    target.intersection_update(common)
    return distinct


def reverse_delta(delta):
    rev_delta = {s: {} for s in delta}
    for s, cn in delta.items():
        for c, n in cn.items():
            rev_delta[n].setdefault(c, set()).add(s)
    return rev_delta


def follow_set(state, char, delta):
    result = set()
    for s in state:
        result.update(delta.get(s, {}).get(char, ()))
    return result


def absorbing_states(rev_delta, accepting):
    absorbing = set(rev_delta) - set(accepting)
    queue = deque(accepting)
    while queue:
        state = queue.popleft()
        prev_set = set()
        for prev in rev_delta[state].values():
            prev_set.update(prev)
        queue.extend(absorbing & prev_set)
        absorbing.difference_update(prev_set)
    return absorbing


def minimize_dfa(start, delta, accepting, alphabet, tags):
    rev_delta = reverse_delta(delta)
    absorbing = absorbing_states(rev_delta, accepting)

    nacc = {}
    acc = {}
    for state in delta:
        if state in absorbing:
            continue
        if state in accepting:
            acc.setdefault(frozenset(tags[state]), set()).add(state)
        else:
            nacc.setdefault(frozenset(tags[state]), set()).add(state)

    partition = list(nacc.values()) + list(acc.values())

    queue = deque(acc.values())

    while queue:
        state = queue.popleft()
        for char in alphabet:
            refiner = follow_set(state, char, rev_delta)
            if refiner:
                for target in partition[:]:
                    refined = inplace_refine(target, refiner)
                    if refined:
                        partition.append(refined)
                        queue.append(refined)

    partition = sorted(tuple(sorted(s)) for s in partition)
    state_map = {}
    new_tags = {}
    for i, state in enumerate(partition):
        new_tags[i] = set()
        for s in state:
            state_map[s] = i
    new_start = 0
    new_accepting = []
    new_delta = {}
    for i, state in enumerate(partition):
        state = state[0]
        new_delta[i] = {}
        new_tags[i] = tags[state]
        if state in accepting:
            new_accepting.append(i)
        for char, n in delta[state].items():
            if n not in absorbing:
                new_delta[i][char] = state_map[n]
    return new_start, new_delta, new_accepting, alphabet, new_tags


class DFA(Regex):

    def __init__(self, start, delta, accepting, alphabet, tags):
        self._start = start
        self._delta = delta
        self._accepting = accepting
        self._alphabet = alphabet
        self._tags = tags

    @classmethod
    def from_vector(cls, vector):
        return DFA(*minimize_dfa(*make_dfa(vector)))

    def __str__(self):
        return "{{{{DFA({})}}}}".format(len(self._delta))

    def nullable(self):
        return self._start in self._accepting

    def alphabet(self):
        return set(self._alphabet)

    def first(self):
        return set(self._delta[self._start])

    def derive(self, char):
        delta = self._delta[self._start]
        if char in delta:
            return DFA(delta[char], self._delta, self._accepting,
                       self._alphabet, self._tags)
        return Empty()

    def choices(self):
        return set([self])

    def tags(self):
        return self._tags[self._start]

    def _key(self):
        return (self._start, id(self._delta), id(self._accepting),
                id(self._alphabet), id(self._tags))

    def conflicts(self):
        return set(tuple(sorted(tags))
                   for tags in self._tags.values() if len(tags) > 1)

    def compact(self):
        def char_ranges(chars):
            ranges = []
            start = None
            end = None
            for char in sorted(chars):
                if start is None:
                    start = end = char
                elif ord(end) + 1 == ord(char):
                    end = char
                else:
                    ranges.append((start, end))
                    start = end = char
            ranges.append((start, end))
            return tuple(ranges)

        c_tags = {k: v for k, v in self._tags.items() if v}
        c_delta = {}
        for state, delta in self._delta.items():
            c_delta[state] = {}
            delta_chars = {}
            for char, next_state in delta.items():
                delta_chars.setdefault(next_state, []).append(char)
            for next_state, chars in delta_chars.items():
                c_delta[state][char_ranges(chars)] = next_state
        return self._start, c_delta, self._accepting, c_tags

    def dot(self):
        start, delta, accepting, tags = self.compact()
        d = ["digraph dfa {", "  rankdir=LR",
             '  "" [shape=none]', '  "" -> "{}"'.format(start)]

        def fmt_ranges(rs):
            fmt = []

            def fmt_range(r):
                if r[0] == r[1]:
                    return fmt_char(r[0])
                if ord(r[0]) + 1 == ord(r[1]):
                    return fmt_char(r[0]) + fmt_char(r[1])
                return "{}-{}".format(fmt_char(r[0]), fmt_char(r[1]))

            def fmt_char(c):
                if c < chr(32) or c > chr(126):
                    return "\\\\x{:02x}".format(ord(c))
                if c in "[]-\\'\"":
                    return "\\" + c
                return c

            if len(rs) == 1 and rs[0][0] == rs[0][1]:
                return fmt_char(rs[0][0])
            for r in rs:
                fmt.append(fmt_range(r))
            return "[{}]".format("".join(fmt))

        for state in delta:
            props = []
            if state in accepting:
                props.append("shape=doublecircle")
            else:
                props.append("shape=circle")
            props.append("fixedsize=shape")
            if state in tags:
                label = "{} {}".format(state, ", ".join(sorted(tags[state])))
                props.append('label="{}"'.format(label))
            d.append('  "{}" [{}]'.format(state, " ".join(props)))
            for chars, n in delta[state].items():
                label = 'label="{}"'.format(fmt_ranges(chars))
                d.append('  "{}" -> "{}" [{}]'.format(state, n, label))
        d.append("}")
        return "\n".join(d)
