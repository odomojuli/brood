"""Multiplication tables -- a quick eyeball of group structure.

The non-zero residues modulo a prime ``p`` form a cyclic (hence abelian)
group under multiplication: every row of the mod-``p`` table is a
permutation of ``1..p-1`` (a Latin square).  Reduce by a composite modulus
and that structure breaks (zero divisors appear).  This module just builds
the tables; the README explains why a scheduler cares about which moduli
generate clean cycles.
"""
from __future__ import annotations

from typing import List, Optional

__all__ = ["multiplication_table", "format_table"]


def multiplication_table(n: int, mod: Optional[int] = None) -> List[List[int]]:
    """Return the ``n x n`` multiplication table (1-indexed).

    If ``mod`` is given, entries are reduced modulo ``mod`` -- use a prime to
    see the cyclic-group (Latin-square) structure.

    >>> multiplication_table(3)
    [[1, 2, 3], [2, 4, 6], [3, 6, 9]]
    >>> multiplication_table(4, mod=5)
    [[1, 2, 3, 4], [2, 4, 1, 3], [3, 1, 4, 2], [4, 3, 2, 1]]
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    rows = range(1, n + 1)
    if mod is None:
        return [[i * j for j in rows] for i in rows]
    return [[(i * j) % mod for j in rows] for i in rows]


def format_table(table: List[List[int]]) -> str:
    """Render a table as right-justified, evenly spaced rows of text."""
    if not table:
        return ""
    width = max(len(str(cell)) for row in table for cell in row)
    lines = ["".join(str(cell).rjust(width + 1) for cell in row) for row in table]
    return "\n".join(lines)
