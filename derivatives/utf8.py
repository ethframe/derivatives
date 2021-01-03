from itertools import groupby
from typing import Iterable, Iterator, List, Tuple

from .core import EMPTY, CharClass, CRegex, Ranges
from .partition import CHARSET_END

MAX_1_BYTE = 0x7F
MAX_2_BYTE = 0x7FF
MAX_3_BYTE = 0xFFFF
MAX_4_BYTE = 0x1FFFFF

SURROGATE_START = 0xD800
SURROGATE_END = 0xDFFF

MAX_CONT_MASK = [
    (MAX_1_BYTE, 0),
    (MAX_2_BYTE, 0x3F),
    (MAX_3_BYTE, 0xFFF),
    (MAX_4_BYTE, 0x3FFFF),
]


def _split_range(lo: int, hi: int) -> Iterator[Tuple[int, int]]:
    for end, mask in MAX_CONT_MASK:
        if lo > end:
            continue
        if hi <= end:
            yield from _split_by_prefix(lo, hi, mask)
            return
        yield from _split_by_prefix(lo, end, mask)
        lo = end + 1


def _split_by_prefix(lo: int, hi: int, mask: int) -> Iterator[Tuple[int, int]]:
    while mask:
        if lo & ~mask != hi & ~mask:
            if lo & mask != 0:
                yield from _split_by_prefix(lo, lo | mask, mask >> 6)
                yield from _split_by_prefix((lo | mask) + 1, hi, mask)
                return
            if hi & mask != mask:
                yield from _split_by_prefix(lo, (hi & ~mask) - 1, mask)
                yield from _split_by_prefix(hi & ~mask, hi, mask >> 6)
                return
        mask >>= 6
    yield (lo, hi)


def split_range(lo: int, hi: int) -> Iterator[Tuple[int, int]]:
    if hi < SURROGATE_START or lo > SURROGATE_END:
        yield from _split_range(lo, hi)
    else:
        if lo < SURROGATE_START:
            yield from _split_range(lo, SURROGATE_START - 1)
        if hi > SURROGATE_END:
            yield from _split_range(SURROGATE_END + 1, hi)


def encode_char(code: int) -> List[int]:
    return list(chr(code).encode('utf-8'))


def encode_range(lo: int, hi: int) -> List[Tuple[int, int]]:
    result: List[Tuple[int, int]] = []
    for lo_b, hi_b in zip(encode_char(lo), encode_char(hi)):
        result.append((lo_b, hi_b))
    return result


def to_byte_regex(lo: int, hi: int) -> CRegex:
    ranges: Ranges = []
    if lo != 0:
        ranges.append((lo - 1, False))
    ranges.append((hi, True))
    if hi != CHARSET_END:
        ranges.append((CHARSET_END, False))
    return CharClass(ranges)


def to_prefix_tree(byte_ranges: Iterable[List[Tuple[int, int]]]) -> CRegex:
    regex: CRegex = EMPTY
    for (lo, hi), items in groupby(byte_ranges, lambda x: x[0]):
        group_regex: CRegex = to_byte_regex(lo, hi)
        tails = [item[1:] for item in items]
        if len(tails) == 1:
            for lo, hi in tails[0]:
                group_regex = group_regex.join(to_byte_regex(lo, hi))
        else:
            group_regex = group_regex.join(to_prefix_tree(tails))
        regex = regex.union(group_regex)
    return regex


def iter_byte_ranges(start: int, end: int) -> Iterator[List[Tuple[int, int]]]:
    for lo, hi in split_range(start, end):
        yield encode_range(lo, hi)


def utf8_range_regex(start: int, end: int) -> CRegex:
    return to_prefix_tree(iter_byte_ranges(start, end))
