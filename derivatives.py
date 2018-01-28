from collections import defaultdict, deque
from itertools import count


__all__ = ("Empty", "Epsilon", "Tag", "AnyChar", "Char", "CharSet",
           "CharRange", "Sequence", "Choice", "Invert", "Repeat", "Intersect",
           "Subtract")


class Regex(object):

    def __str__(self):
        raise NotImplementedError()

    def nullable(self):
        raise NotImplementedError()

    def alphabet(self):
        raise NotImplementedError()

    def first(self):
        raise NotImplementedError()

    def derive(self, char):
        raise NotImplementedError()

    def tags(self):
        raise NotImplementedError()

    def choices(self):
        raise NotImplementedError()

    def prefix(self):
        raise NotImplementedError()

    def __mul__(self, other):
        if isinstance(other, Empty):
            return other
        if isinstance(other, Epsilon):
            return self
        return Sequence(self, other)

    def __or__(self, other):
        if isinstance(self, Epsilon) and isinstance(other, Epsilon):
            return self
        if isinstance(other, Empty):
            return self
        choices = sorted(self.choices() | other.choices())
        regex = choices[0]
        for choice in choices[1:]:
            regex = Choice(regex, choice)
        return regex

    def __and__(self, other):
        if isinstance(other, Empty):
            return other
        if self == other:
            return self
        return Intersect(self, other)

    def __sub__(self, other):
        if isinstance(other, Empty):
            return self
        if self == other:
            return Empty()
        return Subtract(self, other)

    def __invert__(self):
        if isinstance(self, Invert):
            return self._regex
        return Invert(self)

    def star(self):
        if isinstance(self, (Empty, Epsilon, Repeat)):
            return self
        return Repeat(self)

    def plus(self):
        return self * self.star()

    def opt(self):
        return self | Epsilon()

    def _key(self):
        raise NotImplementedError()

    def __eq__(self, other):
        return self.__class__ is other.__class__ and \
            self._key() == other._key()

    def __lt__(self, other):
        return id(self.__class__) < id(other.__class__) or \
            self.__class__ is other.__class__ and \
            self._key() < other._key()

    def __hash__(self):
        val = getattr(self, "_hash", None)
        if val is None:
            self._hash = val = hash((id(self.__class__),) + self._key())
        return val

    def dfa(self):
        return DFA(*minimize_dfa(*make_dfa(self)))


class Empty(Regex):

    def __str__(self):
        return "\\0"

    def nullable(self):
        return False

    def alphabet(self):
        return set()

    def first(self):
        return set()

    def derive(self, char):
        return self

    def tags(self):
        return set()

    def choices(self):
        return set()

    def __mul__(self, other):
        return self

    def __or__(self, other):
        return other

    def __and__(self, other):
        return self

    def __sub__(self, other):
        return self

    def _key(self):
        return ()


class Epsilon(Regex):

    def __str__(self):
        return "\\e"

    def nullable(self):
        return True

    def alphabet(self):
        return set()

    def first(self):
        return set()

    def derive(self, char):
        return Empty()

    def tags(self):
        return set()

    def choices(self):
        return set([self])

    def __mul__(self, other):
        return other

    def _key(self):
        return ()


class Tag(Regex):

    def __init__(self, tag):
        self._tag = tag

    def __str__(self):
        return "{{{}}}".format(self._tag)

    def nullable(self):
        return True

    def alphabet(self):
        return set()

    def first(self):
        return set()

    def derive(self, char):
        return Empty()

    def tags(self):
        return set([self._tag])

    def choices(self):
        return set([self])

    def _key(self):
        return (self._tag,)


class AnyChar(Regex):

    def __str__(self):
        return "."

    def nullable(self):
        return False

    def alphabet(self):
        return set(chr(i) for i in range(256))

    def first(self):
        return set(chr(i) for i in range(256))

    def derive(self, char):
        return Epsilon()

    def tags(self):
        return set()

    def choices(self):
        return set([self])

    def _key(self):
        return ()


class Char(Regex):

    def __init__(self, char):
        self._char = char

    def __str__(self):
        def maybe_escape(char):
            if char in "\\{}()+|&~*?.[]":
                return "\\" + char
            return char
        return maybe_escape(self._char)

    def nullable(self):
        return False

    def alphabet(self):
        return set([self._char])

    def first(self):
        return set([self._char])

    def derive(self, char):
        if char == self._char:
            return Epsilon()
        return Empty()

    def tags(self):
        return set()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._char,)


class CharSet(Regex):

    def __init__(self, chars):
        self._chars = chars

    def __str__(self):
        def maybe_escape(char):
            if char in "\\{}()+|&~*?.[]":
                return "\\" + char
            return char
        return "[{}]".format("".join(map(maybe_escape, self._chars)))

    def nullable(self):
        return False

    def alphabet(self):
        return set(self._chars)

    def first(self):
        return set(self._chars)

    def derive(self, char):
        if char in self._chars:
            return Epsilon()
        return Empty()

    def tags(self):
        return set()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._chars,)


class CharRange(Regex):

    def __init__(self, start, end):
        self._start = start
        self._end = end

    def __str__(self):
        return "[{}-{}]".format(self._start, self._end)

    def nullable(self):
        return False

    def alphabet(self):
        return set(chr(i) for i in range(ord(self._start), ord(self._end) + 1))

    def first(self):
        return set(chr(i) for i in range(ord(self._start), ord(self._end) + 1))

    def derive(self, char):
        if self._start <= char <= self._end:
            return Epsilon()
        return Empty()

    def tags(self):
        return set()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._start, self._end)


class Sequence(Regex):

    def __init__(self, first, second):
        self._first = first
        self._second = second

    def __str__(self):
        def maybe_paren(regex):
            if isinstance(regex, (Choice, Intersect, Subtract)):
                return "({})".format(regex)
            return str(regex)
        return maybe_paren(self._first) + maybe_paren(self._second)

    def nullable(self):
        return self._first.nullable() and self._second.nullable()

    def alphabet(self):
        return self._first.alphabet() | self._second.alphabet()

    def first(self):
        if self._first.nullable():
            return self._first.first() | self._second.first()
        return self._first.first()

    def derive(self, char):
        if self._first.nullable():
            return (self._first.derive(char) * self._second |
                    self._second.derive(char))
        return self._first.derive(char) * self._second

    def tags(self):
        if self._first.nullable():
            return self._first.tags() | self._second.tags()
        return self._first.tags()

    def choices(self):
        return set([self])

    def __mul__(self, other):
        return self._first * (self._second * other)

    def _key(self):
        return (self._first, self._second)


class Choice(Regex):

    def __init__(self, first, second):
        self._first = first
        self._second = second

    def __str__(self):
        def maybe_paren(regex):
            if isinstance(regex, (Intersect, Subtract)):
                return "({})".format(regex)
            return str(regex)
        return "{}|{}".format(maybe_paren(self._first),
                              maybe_paren(self._second))

    def nullable(self):
        return self._first.nullable() or self._second.nullable()

    def alphabet(self):
        return self._first.alphabet() | self._second.alphabet()

    def first(self):
        return self._first.first() | self._second.first()

    def derive(self, char):
        return self._first.derive(char) | self._second.derive(char)

    def tags(self):
        return self._first.tags() | self._second.tags()

    def choices(self):
        return set([self._first, self._second])

    def _key(self):
        return (self._first, self._second)


class Repeat(Regex):

    def __init__(self, regex):
        self._regex = regex

    def __str__(self):
        if isinstance(self._regex, (Empty, Epsilon, Tag, Char, Repeat)):
            return str(self._regex) + "*"
        return "({})*".format(self._regex)

    def nullable(self):
        return True

    def alphabet(self):
        return self._regex.alphabet()

    def first(self):
        return self._regex.first()

    def derive(self, char):
        return self._regex.derive(char) * self

    def tags(self):
        return self._regex.tags()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._regex,)


class Invert(Regex):

    def __init__(self, regex):
        self._regex = regex

    def __str__(self):
        if isinstance(self._regex, (Empty, Epsilon, Tag, Char, Invert)):
            return "~" + str(self._regex)
        return "~({})".format(self._regex)

    def nullable(self):
        return not self._regex.nullable()

    def alphabet(self):
        return set(chr(i) for i in range(256))

    def first(self):
        return set(chr(i) for i in range(256))

    def derive(self, char):
        return ~self._regex.derive(char)

    def tags(self):
        # TODO: invert tags?
        return set()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._regex,)


class Intersect(Regex):

    def __init__(self, first, second):
        self._first = first
        self._second = second

    def __str__(self):
        def maybe_paren(regex):
            if isinstance(regex, (Choice, Subtract)):
                return "({})".format(regex)
            return str(regex)
        return "{}&{}".format(maybe_paren(self._first),
                              maybe_paren(self._second))

    def nullable(self):
        return self._first.nullable() and self._second.nullable()

    def alphabet(self):
        return self._first.alphabet() & self._second.alphabet()

    def first(self):
        return self._first.first() | self._second.first()

    def derive(self, char):
        return self._first.derive(char) & self._second.derive(char)

    def tags(self):
        return self._first.tags() & self._second.tags()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._first, self._second)


class Subtract(Regex):

    def __init__(self, first, second):
        self._first = first
        self._second = second

    def __str__(self):
        def maybe_paren(regex):
            if isinstance(regex, (Choice, Intersect, Subtract)):
                return "({})".format(regex)
            return str(regex)
        return "{}-{}".format(maybe_paren(self._first),
                              maybe_paren(self._second))

    def nullable(self):
        return self._first.nullable() and not self._second.nullable()

    def alphabet(self):
        return self._first.alphabet() | self._second.alphabet()

    def first(self):
        return self._first.first() | self._second.first()

    def derive(self, char):
        return self._first.derive(char) - self._second.derive(char)

    def tags(self):
        return self._first.tags() - self._second.tags()

    def choices(self):
        return set([self])

    def _key(self):
        return (self._first, self._second)


def make_dfa(regex):
    state_map = defaultdict(count().__next__)
    start = state_map[regex]
    queue = deque([(state_map[regex], regex)])
    delta = {}
    tags = {}
    accepting = []
    alphabet = sorted(regex.alphabet())

    while queue:
        state_index, state = queue.popleft()
        delta[state_index] = {}
        tags[state_index] = state.tags()
        if state.nullable():
            accepting.append(state_index)
        for char in state.first():
            next_state = state.derive(char)
            if isinstance(next_state, Empty):
                continue
            l = len(state_map)
            next_index = state_map[next_state]
            if l != len(state_map):
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
    rev_delta = {}
    for s, cn in delta.items():
        for c, n in cn.items():
            rev_delta.setdefault(n, {}).setdefault(c, set()).add(s)
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

    def dfa(self):
        return self

    def conflicts(self):
        return set(tuple(sorted(tags))
                   for tags in self._tags.values() if len(tags) > 1)
