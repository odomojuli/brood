"""Tests for brood.tables -- multiplication tables and group structure."""
from brood.tables import format_table, multiplication_table


def test_plain_table():
    assert multiplication_table(3) == [[1, 2, 3], [2, 4, 6], [3, 6, 9]]


def test_mod_table_exact():
    assert multiplication_table(4, mod=5) == [
        [1, 2, 3, 4],
        [2, 4, 1, 3],
        [3, 1, 4, 2],
        [4, 3, 2, 1],
    ]


def test_prime_modulus_rows_are_latin():
    # (Z/pZ)* is a group: each row of the mod-p table on 1..p-1 is a
    # permutation of 1..p-1 (a Latin square).
    p = 7
    table = multiplication_table(p - 1, mod=p)
    expected = set(range(1, p))
    for row in table:
        assert set(row) == expected


def test_format_table_alignment():
    text = format_table([[1, 2], [3, 40]])
    # Columns right-justified to the widest cell ("40") plus a pad space.
    assert text == "  1  2\n  3 40"
