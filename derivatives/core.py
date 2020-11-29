class Regex:

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
        return []

    def choices(self):
        raise NotImplementedError()

    def __mul__(self, other):
        if isinstance(other, Empty):
            return other
        if isinstance(other, Epsilon):
            return self
        return Sequence(self, other)

    def __or__(self, other):
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

    def choices(self):
        return set([self])

    def __mul__(self, other):
        return other

    def _key(self):
        return ()


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

    def choices(self):
        return self._first.choices() | self._second.choices()

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

    def choices(self):
        return set([self])

    def _key(self):
        return (self._first, self._second)
