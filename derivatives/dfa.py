from collections import defaultdict, deque
from itertools import count
from typing import Dict, List, Optional, Set, Tuple

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


DfaTransitions = List[Tuple[str, str, int]]
DfaDelta = List[DfaTransitions]
DfaTags = List[Optional[List[str]]]


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

    def tags(self) -> Optional[List[str]]:
        return self._tags[self._state]


class Dfa:
    def __init__(self, delta: DfaDelta, tags: DfaTags):
        self._delta = delta
        self._tags = tags

    def start(self) -> DfaRunner:
        return DfaRunner(self._delta, self._tags)

    def conflicts(self) -> Set[Tuple[str, ...]]:
        return set(tuple(sorted(tags))
                   for tags in self._tags if tags and len(tags) > 1)



def make_dfa(vector: Vector) -> Dfa:
    delta: Dict[int, DfaTransitions] = {}
    tags: Dict[int, List[str]] = {}

    state_map: Dict[Vector, int] = defaultdict(count().__next__)
    queue = deque([(state_map[vector], vector)])

    while queue:
        state, vector = queue.popleft()
        state_delta = delta[state] = []
        state_tags = vector.tags()
        if state_tags:
            tags[state] = state_tags

        last = 0
        for end, target in vector.transitions():
            if target.empty():
                last = end
                continue
            len_before = len(state_map)
            target_state = state_map[target]
            if len(state_map) != len_before:
                queue.append((target_state, target))
            state_delta.append((chr(last), chr(end - 1), target_state))

    return Dfa(
        [transitions for _, transitions in sorted(delta.items())],
        [tags.get(i) for i, _ in sorted(delta.items())]
    )
