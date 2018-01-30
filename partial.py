from collections import defaultdict, deque
from itertools import count


class LinearForm(object):

    def __init__(self, items):
        self._items = items

    def __str__(self):
        return "{{{}}}".format(", ".join(map(str, sorted(self._items))))

    def __mul__(self, other):
        if isinstance(other, Regex):
            return LinearForm(set(i * other for i in self._items))
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, LinearForm):
            return LinearForm(self._items | other._items)
        return NotImplemented

    def __iter__(self):
        return iter(sorted(self._items))


class LinearTerm(object):

    def __init__(self, char, tag, regex):
        self._char = char
        self._tag = tag
        self._regex = regex

    def __str__(self):
        return "<{!r}, {!r}, {}>".format(self._char, self._tag, self._regex)

    def __mul__(self, other):
        if isinstance(other, Regex):
            return LinearTerm(self._char, self._tag, self._regex * other)
        return NotImplemented

    def __add__(self, other):
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, LinearTerm):
            return (self._char, self._regex) < (other._char, other._regex)
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, LinearTerm):
            return ((self._char, self._tag, self._regex) ==
                    (other._char, other._tag, other._regex))
        return NotImplemented

    def __hash__(self):
        return hash((self._char, self._tag, self._regex))


class Regex(object):

    def __mul__(self, other):
        if isinstance(other, Epsilon):
            return self
        if isinstance(other, Regex):
            return Sequence(self, other)
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, Empty):
            return self
        if isinstance(other, Choice):
            return Choice(other._choices.union([self]))
        if isinstance(other, Regex):
            if self == other:
                return self
            return Choice(set([self, other]))
        return NotImplemented

    def star(self):
        return Repeat(self)

    def __lt__(self, other):
        if isinstance(other, Regex):
            return self._key() < other._key()
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, Regex):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self):
        return hash((self.__class__,) + self._key())


class Empty(Regex):

    def __str__(self):
        return "\\0"

    def nullable(self):
        return False

    def lf_nullable(self):
        return False

    def linear(self):
        return LinearForm(set())

    def __mul__(self, other):
        if isinstance(other, Regex):
            return self
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, Regex):
            return other
        raise NotImplemented

    def star(self):
        return self

    def _key(self):
        return (id(Empty),)


class Epsilon(Regex):

    def __str__(self):
        return "\\e"

    def nullable(self):
        return True

    def lf_nullable(self):
        return True

    def linear(self):
        return LinearForm(set())

    def __mul__(self, other):
        if isinstance(other, Regex):
            return other
        return NotImplemented

    def star(self):
        return self

    def _key(self):
        return (id(Epsilon),)


class Tag(Regex):

    def __init__(self, tag):
        self._tag = tag

    def __str__(self):
        return "<{}>".format(self._tag)

    def nullable(self):
        return True

    def lf_nullable(self):
        return False

    def linear(self):
        return LinearForm(set([LinearTerm('', self._tag, Tagged())]))

    def _key(self):
        return (id(Tag), self._tag)


class Tagged(Regex):

    def __str__(self):
        return "!"

    def nullable(self):
        return True

    def lf_nullable(self):
        return True

    def linear(self):
        return LinearForm(set())

    def _key(self):
        return (id(Tagged),)


class Char(Regex):

    def __init__(self, char):
        self._char = char

    def __str__(self):
        if self._char in "\\()<>!+*":
            return "\\" + self._char
        return self._char

    def nullable(self):
        return False

    def lf_nullable(self):
        return False

    def linear(self):
        return LinearForm(set([LinearTerm(self._char, None, Epsilon())]))

    def _key(self):
        return (id(Char), self._char)


class Sequence(Regex):

    def __init__(self, head, tail):
        self._head = head
        self._tail = tail

    def __str__(self):
        def maybe_paren(regex):
            if isinstance(regex, Choice):
                return "({})".format(regex)
            return str(regex)
        return maybe_paren(self._head) + maybe_paren(self._tail)

    def nullable(self):
        return self._head.nullable() and self._tail.nullable()

    def lf_nullable(self):
        return self._head.lf_nullable() and self._tail.lf_nullable()

    def linear(self):
        if self._head.lf_nullable():
            return self._head.linear() * self._tail + self._tail.linear()
        return self._head.linear() * self._tail

    def __mul__(self, other):
        if isinstance(other, Regex):
            return Sequence(self._head, self._tail * other)
        return NotImplemented

    def _key(self):
        return (id(Sequence), self._head, self._tail)


class Choice(Regex):

    def __init__(self, choices):
        self._choices = choices

    def __str__(self):
        return "+".join(map(str, sorted(self._choices)))

    def nullable(self):
        return any(c.nullable() for c in self._choices)

    def lf_nullable(self):
        return any(c.lf_nullable() for c in self._choices)

    def linear(self):
        lf = LinearForm(set())
        for c in self._choices:
            lf += c.linear()
        return lf

    def __add__(self, other):
        if isinstance(other, Choice):
            return Choice(self._choices | other._choices)
        if isinstance(other, Regex):
            return Choice(self._choices.union([other]))
        return NotImplemented

    def _key(self):
        return (id(Choice),) + tuple(sorted(self._choices))


class Repeat(Regex):

    def __init__(self, regex):
        self._regex = regex

    def __str__(self):
        if isinstance(self._regex, (Choice, Sequence, Repeat)):
            return "({})*".format(self._regex)
        return str(self._regex) + "*"

    def nullable(self):
        return True

    def lf_nullable(self):
        return True

    def linear(self):
        return self._regex.linear() * self

    def star(self):
        return self

    def _key(self):
        return (id(Repeat), self._regex)


def lt_to_tuple(lt, sm=None):
    if sm is None:
        return (lt._char, lt._tag, lt._regex)
    return (lt._char, lt._tag, sm[lt._regex])


def te_closure(states, delta):
    closure = set(states)
    queue = deque(iterable, maxlen)


def make_nfa(regex):
    sm = defaultdict(count().__next__)
    start = sm[regex]
    delta = {}
    accepting = []

    queue = deque([regex])
    while queue:
        state = queue.popleft()
        state_delta = delta[sm[state]] = {}
        if state.nullable():
            accepting.append(sm[state])
        for lt in sorted(state.linear()):
            char, tag, next_state = lt_to_tuple(lt)
            if next_state not in sm:
                queue.append(next_state)
            state_delta.setdefault(char, set()).add((tag, sm[next_state]))
    
    return start, delta, accepting


def main():
    regex = Char("a").star() * Tag(0) * (Char("a") + Char("b") * Tag(1))
    print(make_nfa(regex))
    

if __name__ == '__main__':
    main()
