from collections import defaultdict, deque
from itertools import count, groupby
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple

from .vector import Vector

DfaTransition = Tuple[int, Optional[int], Optional[str], bool]
DfaTransitions = List[DfaTransition]
DfaDelta = List[DfaTransitions]
DfaTags = List[Optional[str]]


class Dfa:
    def __init__(self, delta: DfaDelta, eof_tags: DfaTags):
        self._delta = delta
        self._eof_tags = eof_tags

    def iter_delta(self) -> Iterator[Tuple[int, DfaTransitions]]:
        return enumerate(self._delta)

    def iter_eof_tags(self) -> Iterator[Tuple[int, Optional[str]]]:
        return enumerate(self._eof_tags)

    def get_eof_tag(self, state: int) -> Optional[str]:
        return self._eof_tags[state]

    def get_tags_set(self) -> Set[str]:
        tags = {tag for tag in self._eof_tags if tag is not None}
        for transitions in self._delta:
            for _, _, tag, _ in transitions:
                if tag is not None:
                    tags.add(tag)
        return tags

    def scan_once(self, input: bytes) -> Optional[Tuple[str, int]]:
        result: Optional[Tuple[str, int]] = None
        state: int = 0
        for pos, code in enumerate(input):
            for end, target, tag, lookahead in self._delta[state]:
                if code < end:
                    if tag is not None:
                        result = (tag, pos if lookahead else pos + 1)
                    if target is None:
                        return result
                    state = target
                    break
        tag = self._eof_tags[state]
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

    while queue:
        state, vector, state_tag = queue.popleft()
        state_delta = delta[state] = []
        if state_tag is not None:
            eof_tags[state] = state_tag

        for end, target in vector.transitions():
            len_before = len(state_map)
            target_state = state_map[target]
            target_tag = resolve_tag(target.tags())
            if len(state_map) != len_before:
                queue.append((target_state, target, target_tag))

            state_delta.append((end, target_state))
            incoming[target_state].add(state)

    lookahead_states: Set[int] = set()
    live = set(eof_tags)
    live_queue = deque(eof_tags)
    while live_queue:
        state = live_queue.popleft()
        for source_state in incoming[state]:
            lookahead_states.add(source_state)
            if source_state not in live:
                live.add(source_state)
                live_queue.append(source_state)

    definite_states = live - lookahead_states
    new_to_old = sorted(lookahead_states)
    old_to_new = dict((state, i) for i, state in enumerate(new_to_old))

    pruned_delta: DfaDelta = []
    for old_state in new_to_old:
        source_tag = eof_tags.get(old_state)
        transitions: DfaTransitions = []
        for end, old_target in delta[old_state]:
            lookahead = old_target not in definite_states
            tag = eof_tags.get(old_target)
            if lookahead and tag is None:
                tag = source_tag
            transitions.append(
                (end, old_to_new.get(old_target), tag, lookahead)
            )
        pruned_delta.append(compress_transitions(transitions))
    pruned_eof_tags = [eof_tags.get(old_state) for old_state in new_to_old]

    return Dfa(pruned_delta, pruned_eof_tags)


def compress_transitions(transitions: DfaTransitions) -> DfaTransitions:
    result: DfaTransitions = []
    for _, group in groupby(transitions, lambda x: (x[1], x[2])):
        result.append(list(group)[-1])
    return result
