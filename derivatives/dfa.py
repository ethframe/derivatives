from collections import deque
from itertools import groupby
from typing import (
    Callable, Deque, Dict, Iterator, List, NamedTuple, Optional, Set, Tuple
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


class _State:
    def __init__(self, tag: Optional[str] = None):
        self.index: Optional[int] = None
        self.transitions: List[Tuple[int, _State, Optional[str]]] = []
        self.incoming: List[_State] = []
        self.tag = tag
        self.live = False


def make_dfa(vector: Vector, tag_resolver: Callable[[List[int]], str]) -> Dfa:
    state = _State()
    vector_to_index: Dict[Vector, int] = {vector: 0}
    states: List[_State] = [state]
    tags: Set[str] = set()
    queue = deque([(state, vector)])
    live_queue: Deque[_State] = deque()

    while queue:
        source, source_vector = queue.popleft()

        for end, target_vector in source_vector.transitions():
            target_tag: Optional[str] = None
            target_tags = target_vector.tags()
            if target_tags:
                target_tag = tag_resolver(target_tags)
                tags.add(target_tag)
                source.live = True
                live_queue.append(source)
            target_vector = target_vector.remove_epsilon()

            new_index = len(states)
            target_index = vector_to_index.setdefault(target_vector, new_index)
            if target_index == new_index:
                target = _State(target_tag)
                states.append(target)
                queue.append((target, target_vector))
            else:
                target = states[target_index]
                if target.tag != target_tag:
                    target.tag = None

            source.transitions.append((end, target, target_tag))
            target.incoming.append(source)

    while live_queue:
        target = live_queue.popleft()
        for source in target.incoming:
            if not source.live:
                source.live = True
                live_queue.append(source)

    states = [state for state in states if state.live]
    for index, state in enumerate(states):
        state.index = index

    dfa_states: List[DfaState] = []
    for state in states:
        lookahead = False
        transitions: DfaTransitions = []
        for end, target, tag in state.transitions:
            lookahead |= tag is not None
            at_exit = False
            if target.live and target.tag is not None:
                tag = None
            elif tag is None and state.tag is not None:
                tag = state.tag
                at_exit = True
            transitions.append(DfaTransition(end, target.index, tag, at_exit))

        dfa_states.append(
            DfaState(
                entry_tag=None if lookahead else state.tag,
                eof_tag=state.tag if lookahead else None,
                transitions=compress_transitions(transitions)
            )
        )

    return Dfa(dfa_states, sorted(tags))


def compress_transitions(transitions: DfaTransitions) -> DfaTransitions:
    result: DfaTransitions = []
    for _, group in groupby(transitions, lambda x: x[1:]):
        result.append(list(group)[-1])
    return result
