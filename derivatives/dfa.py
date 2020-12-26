from collections import defaultdict, deque
from itertools import count, groupby
from typing import (
    Callable, Dict, Iterator, List, NamedTuple, Optional, Set, Tuple
)

from .vector import Vector


class DfaTransition(NamedTuple):
    end: int
    target: Optional[int]
    tag: Optional[str]
    at_exit: bool


DfaTransitions = List[DfaTransition]


class DfaState(NamedTuple):
    entry_tag: Optional[str]
    eof_tag: Optional[str]
    transitions: DfaTransitions


class Dfa:
    def __init__(self, states: List[DfaState], tags: List[str]):
        self._states = states
        self._tags = tags

    def iter_states(self) -> Iterator[Tuple[int, DfaState]]:
        return enumerate(self._states)

    def get_tags(self) -> List[str]:
        return self._tags

    def scan_once(self, input: bytes) -> Optional[Tuple[str, int]]:
        result: Optional[Tuple[str, int]] = None
        state: int = 0
        for pos, code in enumerate(input):
            entry, _, transitions = self._states[state]
            if entry is not None:
                result = (entry, pos)
            for end, target, tag, at_exit in transitions:
                if code < end:
                    if tag is not None:
                        result = (tag, pos if at_exit else pos + 1)
                    if target is None:
                        return result
                    state = target
                    break
        tag = self._states[state].eof_tag
        if tag is not None:
            result = (tag, len(input))
        return result

    def scan_all(self, input: bytes) -> Iterator[Tuple[str, bytes]]:
        while input:
            result = self.scan_once(input)
            if result is None:
                raise ValueError("Input not recognized")
            tag, pos = result
            yield tag, input[:pos]
            input = input[pos:]


def make_dfa(vector: Vector, tag_resolver: Callable[[Set[int]], str]) -> Dfa:

    def resolve_tag(tags: Set[int]) -> Optional[str]:
        if tags:
            return tag_resolver(tags)
        return None

    delta: Dict[int, List[Tuple[int, int]]] = {}
    eof_tags: Dict[int, str] = {}

    state_map: Dict[Vector, int] = defaultdict(count().__next__)
    queue = deque([(state_map[vector], vector, resolve_tag(vector.tags()))])

    incoming: Dict[int, Set[int]] = defaultdict(set)

    lookahead_states: Set[int] = set()
    while queue:
        state, vector, state_tag = queue.popleft()
        state_delta = delta[state] = []
        if state_tag is not None:
            eof_tags[state] = state_tag

        any_target_has_tag = False
        for end, target in vector.transitions():
            len_before = len(state_map)
            target_state = state_map[target]
            target_tag = resolve_tag(target.tags())
            any_target_has_tag |= target_tag is not None
            if len(state_map) != len_before:
                queue.append((target_state, target, target_tag))

            state_delta.append((end, target_state))
            incoming[target_state].add(state)
        if any_target_has_tag:
            lookahead_states.add(state)

    without_transitions = set(eof_tags)
    live = set(eof_tags)
    live_queue = deque(eof_tags)
    while live_queue:
        state = live_queue.popleft()
        for source_state in incoming[state]:
            without_transitions.discard(source_state)
            if source_state not in live:
                live.add(source_state)
                live_queue.append(source_state)

    new_to_old = sorted(live - without_transitions)
    old_to_new = dict((state, i) for i, state in enumerate(new_to_old))

    states: List[DfaState] = []
    for old_state in new_to_old:
        source_tag = eof_tags.get(old_state)
        transitions: DfaTransitions = []
        use_lookahead = old_state in lookahead_states
        for end, old_target in delta[old_state]:
            at_exit = old_target not in without_transitions
            if at_exit:
                tag: Optional[str] = None
                if use_lookahead and eof_tags.get(old_target) is None:
                    tag = source_tag
            else:
                tag = eof_tags.get(old_target)
            transitions.append(
                DfaTransition(end, old_to_new.get(old_target), tag, at_exit)
            )
        states.append(
            DfaState(
                entry_tag=None if use_lookahead else source_tag,
                eof_tag=source_tag if use_lookahead else None,
                transitions=compress_transitions(transitions)
            )
        )

    return Dfa(states, sorted(set(eof_tags.values())))


def compress_transitions(transitions: DfaTransitions) -> DfaTransitions:
    result: DfaTransitions = []
    for _, group in groupby(transitions, lambda x: (x[1], x[2])):
        result.append(list(group)[-1])
    return result
