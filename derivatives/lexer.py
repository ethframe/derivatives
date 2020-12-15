from typing import Callable, Dict, List, Set, Tuple

from .core import Regex
from .dfa import Dfa, make_dfa
from .vector import Vector, VectorItem

TagResolver = Callable[[Set[int], Dict[int, str]], str]


def select_first(tags: Set[int], names: Dict[int, str]) -> str:
    return names[min(tags)]


def raise_on_conflict(tags: Set[int], names: Dict[int, str]) -> str:
    if len(tags) == 1:
        return names[next(iter(tags))]
    raise ValueError(
        "Conflicting patterns: {}".format(
            ", ".join(names[tag] for tag in sorted(tags))
        )
    )


def make_lexer(
        tokens: List[Tuple[str, Regex]],
        tag_resolver: TagResolver = raise_on_conflict) -> Dfa:

    items: List[VectorItem] = []
    names: Dict[int, str] = {}
    for i, (name, regex) in enumerate(tokens):
        items.append((i, regex))
        names[i] = name

    def dfa_tag_resolver(tags: Set[int]) -> str:
        return tag_resolver(tags, names)

    return make_dfa(Vector(items), dfa_tag_resolver)
