import sys
from typing import List, Optional, Set, Tuple


class Scanner:
    def __init__(self, chars: str):
        self._chars = chars
        self._pos = 0
        self.char = None if len(chars) < 1 else chars[0]

    def advance(self, n: int = 1) -> None:
        if self._pos + n < len(self._chars):
            self._pos += n
            self.char = self._chars[self._pos]
        else:
            self._pos = len(self._chars)
            self.char = None

    def expect(self, char: str) -> bool:
        if self.char == char:
            self.advance()
            return True
        return False

    def consume(self, n: int, chars: Set[str]) -> Optional[str]:
        if self._pos + n > len(self._chars):
            return None
        start = end = self._pos
        for _ in range(n):
            if self._chars[end] not in chars:
                return None
            end += 1
        self.advance(n)
        return self._chars[start:end]


def parse_char_set(chars: str) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    scanner = Scanner(chars)

    invert = scanner.expect("^")

    def add_range(start: int, end: Optional[int] = None) -> None:
        if end is None:
            end = start
        if invert:
            if start > 0:
                ranges.append((0, start - 1))
            if end < sys.maxunicode:
                ranges.append((end + 1, sys.maxunicode))
        else:
            ranges.append((start, end))

    while scanner.char:
        if scanner.expect("\\"):
            code = parse_escape(scanner)
        else:
            code = ord(scanner.char)
            scanner.advance()
        if scanner.expect("-"):
            if scanner.char is None:
                add_range(code)
                add_range(ord("-"))
                break
            if scanner.expect("\\"):
                end = parse_escape(scanner)
            else:
                end = ord(scanner.char)
                scanner.advance()
            if code > end:
                raise ValueError("Invalid range")
            add_range(code, end)
        else:
            add_range(code)

    if not ranges:
        return [(0, sys.maxunicode)] if invert else []

    result: List[Tuple[int, int]] = []
    ranges.sort()
    it = iter(ranges)
    last_start, last_end = next(it)
    for start, end in it:
        if start < last_end:
            last_end = end
        else:
            result.append((last_start, last_end))
            last_start = start
            last_end = end
    result.append((last_start, last_end))
    return result


ESCAPES = {
    "b": ord("\b"),
    "f": ord("\f"),
    "n": ord("\n"),
    "r": ord("\r"),
    "t": ord("\t"),
}

HEX_DIGITS = set("0123456789abcdefABCDEF")
HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}


def parse_escape(scanner: Scanner) -> int:
    char = scanner.char
    if char is None:
        raise ValueError("Invalid escape")
    scanner.advance()

    if char in ESCAPES:
        return ESCAPES[char]

    if char in HEX_ESCAPES:
        val = scanner.consume(HEX_ESCAPES[char], HEX_DIGITS)
        if val is None:
            raise ValueError("Invalid hex escape")
        code = int(val, 16)
        if code > sys.maxunicode:
            raise ValueError("Invalid hex escape")
        return code

    return ord(char)
