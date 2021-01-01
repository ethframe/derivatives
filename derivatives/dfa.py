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

    delta: Dict[int, List[Tuple[int, int, Optional[str]]]] = {}

    tags = set()
    state_map: Dict[Vector, int] = defaultdict(count().__next__)
    queue = deque([(state_map[vector], vector)])

    incoming: Dict[int, List[Tuple[int, Optional[str]]]] = defaultdict(list)

    single_tag_states: Dict[int, Optional[str]] = {}
    lookahead_states: Set[int] = set()
    while queue:
        state, vector = queue.popleft()
        state_delta = delta[state] = []

        for end, target in vector.transitions():
            target_tag = resolve_tag(target.tags())
            if target_tag is not None:
                tags.add(target_tag)
                lookahead_states.add(state)

            target = target.remove_epsilon()

            len_before = len(state_map)
            target_state = state_map[target]
            if len(state_map) != len_before:
                queue.append((target_state, target))
                single_tag_states[target_state] = target_tag
            elif target_state in single_tag_states:
                if single_tag_states[target_state] != target_tag:
                    del single_tag_states[target_state]

            state_delta.append((end, target_state, target_tag))
            incoming[target_state].append((state, target_tag))

    state_tag: Dict[int, str] = {}
    live = set(lookahead_states)
    live_queue = deque(lookahead_states)
    while live_queue:
        state = live_queue.popleft()
        tag = single_tag_states.get(state)
        if tag is not None:
            state_tag[state] = tag
        for source_state, tag in incoming[state]:
            if source_state not in live:
                live.add(source_state)
                live_queue.append(source_state)

    new_to_old = sorted(live)
    old_to_new = dict((state, i) for i, state in enumerate(new_to_old))

    states: List[DfaState] = []
    for old_state in new_to_old:
        source_tag = state_tag.get(old_state)
        transitions: DfaTransitions = []
        use_lookahead = old_state in lookahead_states
        for end, old_target, tag in delta[old_state]:
            at_exit = False
            if old_target in state_tag:
                tag = None
            elif tag is None:
                tag = source_tag
                at_exit = True
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

    return Dfa(states, sorted(tags))


def compress_transitions(transitions: DfaTransitions) -> DfaTransitions:
    result: DfaTransitions = []
    for _, group in groupby(transitions, lambda x: x[1:]):
        result.append(list(group)[-1])
    return result
