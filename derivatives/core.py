from .partition import CHARSET_END, Partition, make_merge_fn, make_update_fn

Derivatives = Partition['Regex']


class Regex:

    def __str__(self):
        raise NotImplementedError()

    def nullable(self):
        raise NotImplementedError()

    def alphabet(self):
        raise NotImplementedError()

    def derive(self, char):
        raise NotImplementedError()

    def derivatives(self) -> Derivatives:
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

    def derive(self, char):
        return self

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

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

    def derive(self, char):
        return Empty()

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Empty())]

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
        return set(chr(i) for i in range(CHARSET_END))

    def derive(self, char):
        return Epsilon()

    def derivatives(self) -> Derivatives:
        return [(CHARSET_END, Epsilon())]

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

    def derive(self, char):
        if char == self._char:
            return Epsilon()
        return Empty()

    def derivatives(self) -> Derivatives:
        result: Derivatives = []
        start = ord(self._char)
        end = start + 1
        if start > 0:
            result.append((start, Empty()))
        result.append((end, Epsilon()))
        if CHARSET_END > end:
            result.append((CHARSET_END, Empty()))
        return result

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

    def derive(self, char):
        if char in self._chars:
            return Epsilon()
        return Empty()

    def derivatives(self) -> Derivatives:
        result: Derivatives = []
        last = 0
        for char in sorted(self._chars):
            start = ord(char)
            end = start + 1
            if start > last:
                result.append((start, Empty()))
            result.append((end, Epsilon()))
            last = end
        if CHARSET_END > last:
            result.append((CHARSET_END, Empty()))
        return result

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

    def derive(self, char):
        if self._start <= char <= self._end:
            return Epsilon()
        return Empty()

    def derivatives(self) -> Derivatives:
        result: Derivatives = []
        start = ord(self._start)
        end = ord(self._end) + 1
        if start > 0:
            result.append((start, Empty()))
        result.append((end, Epsilon()))
        if CHARSET_END > end:
            result.append((CHARSET_END, Empty()))
        return result

    def choices(self):
        return set([self])

    def _key(self):
        return (self._start, self._end)


def append_item(left: Regex, right: Regex) -> Regex:
    return left * right


append_items = make_update_fn(append_item)


def merge_choice_item(left: Regex, right: Regex) -> Regex:
    return left | right


merge_choice = make_merge_fn(merge_choice_item, merge_choice_item)


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

    def derive(self, char):
        if self._first.nullable():
            return (self._first.derive(char) * self._second |
                    self._second.derive(char))
        return self._first.derive(char) * self._second

    def derivatives(self) -> Derivatives:
        result = append_items(self._first.derivatives(), self._second)
        if self._first.nullable():
            result = merge_choice(result, self._second.derivatives())
        return result

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

    def derive(self, char):
        return self._first.derive(char) | self._second.derive(char)

    def derivatives(self) -> Derivatives:
        return merge_choice(self._first.derivatives(),
                            self._second.derivatives())

    def choices(self):
        return self._first.choices() | self._second.choices()

    def _key(self):
        return (self._first, self._second)


class Repeat(Regex):

    def __init__(self, regex):
        self._regex = regex

    def __str__(self):
        if isinstance(self._regex, (Empty, Epsilon, Char, Repeat)):
            return str(self._regex) + "*"
        return "({})*".format(self._regex)

    def nullable(self):
        return True

    def alphabet(self):
        return self._regex.alphabet()

    def derive(self, char):
        return self._regex.derive(char) * self

    def derivatives(self) -> Derivatives:
        return append_items(self._regex.derivatives(), self)

    def choices(self):
        return set([self])

    def _key(self):
        return (self._regex,)


class Invert(Regex):

    def __init__(self, regex):
        self._regex = regex

    def __str__(self):
        if isinstance(self._regex, (Empty, Epsilon, Char, Invert)):
            return "~" + str(self._regex)
        return "~({})".format(self._regex)

    def nullable(self):
        return not self._regex.nullable()

    def alphabet(self):
        return set(chr(i) for i in range(CHARSET_END))

    def derive(self, char):
        return ~self._regex.derive(char)

    def derivatives(self) -> Derivatives:
        return [(end, ~item) for end, item in self._regex.derivatives()]

    def choices(self):
        return set([self])

    def _key(self):
        return (self._regex,)


def merge_intersect_item(left: Regex, right: Regex) -> Regex:
    return left & right


merge_intersect = make_merge_fn(merge_intersect_item, merge_intersect_item)


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

    def derive(self, char):
        return self._first.derive(char) & self._second.derive(char)

    def derivatives(self) -> Derivatives:
        return merge_intersect(self._first.derivatives(),
                               self._second.derivatives())

    def choices(self):
        return set([self])

    def _key(self):
        return (self._first, self._second)


def merge_subtract_item(left: Regex, right: Regex) -> Regex:
    return left - right


merge_subtract = make_merge_fn(merge_subtract_item, merge_subtract_item)


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

    def derive(self, char):
        return self._first.derive(char) - self._second.derive(char)

    def derivatives(self) -> Derivatives:
        return merge_subtract(self._first.derivatives(),
                              self._second.derivatives())

    def choices(self):
        return set([self])

    def _key(self):
        return (self._first, self._second)
