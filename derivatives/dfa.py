from collections import defaultdict, deque
from itertools import count, groupby
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple

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

    def handle(self, code: int) -> bool:
        state = self._state
        if state is None:
            return False
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

    def iter_delta(self) -> Iterator[Tuple[int, DfaTransitions]]:
        return enumerate(self._delta)

    def iter_eof_tags(self) -> Iterator[Tuple[int, Optional[str]]]:
        return enumerate(self._eof_tags)

    def get_tags_set(self) -> Set[str]:
        tags = {tag for tag in self._eof_tags if tag is not None}
        for transitions in self._delta:
            for _, _, tag in transitions:
                if tag is not None:
                    tags.add(tag)
        return tags

    def start(self) -> DfaRunner:
        return DfaRunner(self._delta, self._eof_tags)

    def scan_once(self, input: bytes) -> Optional[Tuple[str, int]]:
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

            transition_tag: Optional[str] = None
            if target_tag is None:
                transition_tag = state_tag

            state_delta.append((end, target_state, transition_tag))
            incoming[target_state].add(state)

    live = set(eof_tags)
    live_queue = deque(eof_tags)
    while live_queue:
        state = live_queue.popleft()
        for source_state in incoming[state]:
            if source_state not in live:
                live.add(source_state)
                live_queue.append(source_state)

    new_to_old = sorted(live)
    old_to_new = dict((state, i) for i, state in enumerate(new_to_old))

    pruned_delta = [
        compress_transitions([
            (end, old_to_new.get(target, None), tag)
            for end, target, tag in delta[old_state]
        ])
        for old_state in new_to_old
    ]
    pruned_eof_tags = [
        eof_tags.get(old_state, None) for old_state in new_to_old
    ]

    return Dfa(pruned_delta, pruned_eof_tags)


def compress_transitions(transitions: DfaTransitions) -> DfaTransitions:
    result: DfaTransitions = []
    for _, group in groupby(transitions, lambda x: (x[1], x[2])):
        result.append(list(group)[-1])
    return result
