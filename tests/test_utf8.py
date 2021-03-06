from derivatives.lexer import make_lexer
import pytest

from derivatives.utf8 import encode_range, split_range

ENCODE_DATA = [
    (
        0x0400, 0x04FF,
        [
            [(0xD0, 0xD3), (0x80, 0xBF)],
        ]
    ),
    (
        0x0400, 0x052F,
        [
            [(0xD0, 0xD3), (0x80, 0xBF)],
            [(0xD4, 0xD4), (0x80, 0xAF)],
        ]
    ),
    (
        0x0E0031, 0x0E0043,
        [
            [(0xF3, 0xF3), (0xA0, 0xA0), (0x80, 0x80), (0xB1, 0xBF)],
            [(0xF3, 0xF3), (0xA0, 0xA0), (0x81, 0x81), (0x80, 0x83)],
        ]
    ),
    (
        0x0000, 0xFFFF,
        [
            [(0x00, 0x7F)],
            [(0xC2, 0xDF), (0x80, 0xBF)],
            [(0xE0, 0xE0), (0xA0, 0xBF), (0x80, 0xBF)],
            [(0xE1, 0xEC), (0x80, 0xBF), (0x80, 0xBF)],
            [(0xED, 0xED), (0x80, 0x9F), (0x80, 0xBF)],
            [(0xEE, 0xEF), (0x80, 0xBF), (0x80, 0xBF)],
        ]
    ),
    (
        0x0000, 0x10FFFF,
        [
            [(0x00, 0x7F)],
            [(0xC2, 0xDF), (0x80, 0xBF)],
            [(0xE0, 0xE0), (0xA0, 0xBF), (0x80, 0xBF)],
            [(0xE1, 0xEC), (0x80, 0xBF), (0x80, 0xBF)],
            [(0xED, 0xED), (0x80, 0x9F), (0x80, 0xBF)],
            [(0xEE, 0xEF), (0x80, 0xBF), (0x80, 0xBF)],
            [(0xF0, 0xF0), (0x90, 0xBF), (0x80, 0xBF), (0x80, 0xBF)],
            [(0xF1, 0xF3), (0x80, 0xBF), (0x80, 0xBF), (0x80, 0xBF)],
            [(0xF4, 0xF4), (0x80, 0x8F), (0x80, 0xBF), (0x80, 0xBF)],
        ]
    )
]


@pytest.mark.parametrize("lo, hi, expect", ENCODE_DATA)
def test_encode_ranges(lo, hi, expect):
    result = [
        encode_range(a, b) for a, b in split_range(lo, hi)
    ]
    assert result == expect
