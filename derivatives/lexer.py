from typing import Callable, Dict, List, Tuple

from .dfa import Dfa, make_dfa
from .edsl import Regex
from .vector import Vector, VectorItem

TagResolver = Callable[[List[int], Dict[int, str]], str]


def select_first(tags: List[int], names: Dict[int, str]) -> str:
    return names[tags[0]]


def raise_on_conflict(tags: List[int], names: Dict[int, str]) -> str:
    if len(tags) == 1:
        return names[tags[0]]
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
        items.append((i, regex.getvalue()))
        names[i] = name

    def dfa_tag_resolver(tags: List[int]) -> str:
        return tag_resolver(tags, names)

    return make_dfa(Vector(items), dfa_tag_resolver)
