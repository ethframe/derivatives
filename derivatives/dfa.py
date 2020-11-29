from collections import defaultdict, deque
from itertools import count
from typing import (
    Any, DefaultDict, Dict, FrozenSet, List, Optional, Set, Tuple
)

from .core import Empty, Regex
from .partition import CHARSET_END, Partition, make_merge_fn


def merge_partial_item(acc: List[Regex], val: Regex) -> List[Regex]:
    acc_copy = acc.copy()
    acc_copy.append(val)
    return acc_copy


def merge_partial_item_inplace(acc: List[Regex], val: Regex) -> List[Regex]:
    acc.append(val)
    return acc


merge_partial = make_merge_fn(merge_partial_item, merge_partial_item_inplace)


Transitions = Partition['Vector']


class Vector:
    def __init__(self, items: List[Tuple[str, Regex]]):
        self._items = items

    def transitions(self) -> Transitions:
        tags: List[str] = []
        partial: Partition[List[Regex]] = [(CHARSET_END, [])]
        for tag, regex in self._items:
            tags.append(tag)
            partial = merge_partial(partial, regex.derivatives())
        return [
            (end, Vector([(tag, regex) for tag, regex in zip(tags, regexes)
                          if not isinstance(regex, Empty)]))
            for end, regexes in partial
        ]

    def empty(self) -> bool:
        return all(isinstance(regex, Empty) for _, regex in self._items)

    def alphabet(self) -> Set[str]:
        result: Set[str] = set()
        for _, regex in self._items:
            result |= regex.alphabet()
        return result

    def tags(self) -> List[str]:
        return [tag for tag, regex in self._items if regex.nullable()]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return self._items == other._items

    def __hash__(self) -> int:
        return hash((Vector, tuple(self._items)))


def make_dfa(vector: Vector
             ) -> Tuple[int, Dict[int, Dict[str, int]], List[int], List[str],
                        Dict[int, List[str]]]:
    state_map: DefaultDict[Vector, int] = defaultdict(count().__next__)
    start = state_map[vector]
    queue = deque([(state_map[vector], vector)])
    delta: Dict[int, Dict[str, int]] = {}
    tags = {}
    accepting = []
    alphabet = sorted(vector.alphabet())

    while queue:
        state_index, state = queue.popleft()
        state_delta = delta[state_index] = {}
        state_tags = tags[state_index] = state.tags()
        if state_tags:
            accepting.append(state_index)
        last = 0
        for end, next_state in state.transitions():
            if next_state.empty():
                last = end
                continue
            sm_len = len(state_map)
            next_index = state_map[next_state]
            if sm_len != len(state_map):
                queue.append((next_index, next_state))
            for char in range(last, end):
                state_delta[chr(char)] = next_index
            last = end

    return start, delta, accepting, alphabet, tags


def inplace_refine(target: Set[int], refiner: Set[int]) -> Optional[Set[int]]:
    common = target & refiner
    if not common:
        return None
    if len(common) * 2 < len(target):
        target.difference_update(refiner)
        return common
    distinct = target - common
    target.intersection_update(common)
    return distinct


def reverse_delta(delta: Dict[int, Dict[str, int]]
                  ) -> Dict[int, Dict[str, Set[int]]]:
    rev_delta: Dict[int, Dict[str, Set[int]]] = {s: {} for s in delta}
    for s, cn in delta.items():
        for c, n in cn.items():
            rev_delta[n].setdefault(c, set()).add(s)
    return rev_delta


def follow_set(state: Set[int], char: str,
               delta: Dict[int, Dict[str, Set[int]]]) -> Set[int]:
    result: Set[int] = set()
    for s in state:
        result.update(delta.get(s, {}).get(char, set()))
    return result


def absorbing_states(rev_delta: Dict[int, Dict[str, Set[int]]],
                     accepting: List[int]) -> Set[int]:
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


def minimize_dfa(start: int, delta: Dict[int, Dict[str, int]],
                 accepting: List[int], alphabet: List[str],
                 tags: Dict[int, List[str]]
                 ) -> Tuple[int, Dict[int, Dict[str, int]], List[int],
                            List[str], Dict[int, List[str]]]:
    rev_delta = reverse_delta(delta)
    absorbing = absorbing_states(rev_delta, accepting)

    nacc: Dict[FrozenSet[str], Set[int]] = {}
    acc: Dict[FrozenSet[str], Set[int]] = {}
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
        state_tmp = queue.popleft()
        for char in alphabet:
            refiner = follow_set(state_tmp, char, rev_delta)
            if refiner:
                for target in partition[:]:
                    refined = inplace_refine(target, refiner)
                    if refined:
                        partition.append(refined)
                        queue.append(refined)

    partition_new = sorted(tuple(sorted(s)) for s in partition)
    state_map: Dict[int, int] = {}
    new_tags: Dict[int, List[str]] = {}
    for i, state_new in enumerate(partition_new):
        new_tags[i] = []
        for s in state_new:
            state_map[s] = i
    new_start = 0
    new_accepting: List[int] = []
    new_delta: Dict[int, Dict[str, int]] = {}
    for i, state_new in enumerate(partition_new):
        state = state_new[0]
        new_delta[i] = {}
        new_tags[i] = tags[state]
        if state in accepting:
            new_accepting.append(i)
        for char, n in delta[state].items():
            if n not in absorbing:
                new_delta[i][char] = state_map[n]
    return new_start, new_delta, new_accepting, alphabet, new_tags


class DFA(Regex):

    def __init__(self, start: int, delta: Dict[int, Dict[str, int]],
                 accepting: List[int], alphabet: List[str],
                 tags: Dict[int, List[str]]):
        self._start = start
        self._delta = delta
        self._accepting = accepting
        self._alphabet = alphabet
        self._tags = tags

    @classmethod
    def from_vector(cls, vector: Vector) -> 'DFA':
        return DFA(*minimize_dfa(*make_dfa(vector)))

    def __str__(self) -> str:
        return "{{{{DFA({})}}}}".format(len(self._delta))

    def nullable(self) -> bool:
        return self._start in self._accepting

    def alphabet(self) -> Set[str]:
        return set(self._alphabet)

    def derive(self, char: str) -> Regex:
        delta = self._delta[self._start]
        if char in delta:
            return DFA(delta[char], self._delta, self._accepting,
                       self._alphabet, self._tags)
        return Empty()

    def choices(self) -> Set[Regex]:
        return set([self])

    def tags(self) -> List[str]:
        return self._tags[self._start]

    def _key(self) -> Tuple[Any, ...]:
        return (self._start, id(self._delta), id(self._accepting),
                id(self._alphabet), id(self._tags))

    def conflicts(self) -> Set[Tuple[str, ...]]:
        return set(tuple(sorted(tags))
                   for tags in self._tags.values() if len(tags) > 1)

    def compact(self) -> Tuple[int,
                               Dict[int,
                                    Dict[Tuple[Tuple[str, str], ...], int]],
                               List[int], Dict[int, List[str]]]:
        def char_ranges(chars: List[str]) -> Tuple[Tuple[str, str], ...]:
            ranges: List[Tuple[str, str]] = []
            start = ''
            end = ''
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
        c_delta: Dict[int, Dict[Tuple[Tuple[str, str], ...], int]] = {}
        for state, delta in self._delta.items():
            c_delta[state] = {}
            delta_chars: Dict[int, List[str]] = {}
            for char, next_state in delta.items():
                delta_chars.setdefault(next_state, []).append(char)
            for next_state, chars in delta_chars.items():
                c_delta[state][char_ranges(chars)] = next_state
        return self._start, c_delta, self._accepting, c_tags

    def dot(self) -> str:
        start, delta, accepting, tags = self.compact()
        d = ["digraph dfa {", "  rankdir=LR",
             '  "" [shape=none]', '  "" -> "{}"'.format(start)]

        def fmt_ranges(rs: Tuple[Tuple[str, str], ...]) -> str:
            fmt = []

            def fmt_range(r: Tuple[str, str]) -> str:
                if r[0] == r[1]:
                    return fmt_char(r[0])
                if ord(r[0]) + 1 == ord(r[1]):
                    return fmt_char(r[0]) + fmt_char(r[1])
                return "{}-{}".format(fmt_char(r[0]), fmt_char(r[1]))

            def fmt_char(c: str) -> str:
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
