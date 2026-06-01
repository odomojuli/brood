"""Hamming numbers -- the regular / 5-smooth / Babylonian numbers.

A Hamming number has the form ``H = 2**i * 3**j * 5**k`` for non-negative
integers ``i, j, k``.  The sequence begins::

    1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 16, 18, 20, 24, 25, 27, ...

    OEIS A051037: https://oeis.org/A051037

The classic lazy generator is due to Dijkstra (*A Discipline of
Programming*, 1976): emit 1, then merge the streams ``2H``, ``3H`` and
``5H``.  Implemented here with ``itertools.tee`` so the three feedback
copies share one underlying sequence and memory stays bounded.

Why ``brood`` cares: 60 = 2**2 * 3 * 5, 3600 = 2**4 * 3**2 * 5**2, and
86400 (= seconds/day) are all Hamming numbers, so "round" calendar
intervals cluster on this set.  Scheduling on its *complement* -- numbers
with a prime factor greater than 5 (OEIS A279622) -- is how you stay off
the beaten beat.
"""
from __future__ import annotations

from itertools import islice, tee
from typing import Iterator, List

__all__ = [
    "hamming",
    "first_n_hamming",
    "hamming_up_to",
    "is_hamming",
]


def _times(factor: int, stream: Iterator[int]) -> Iterator[int]:
    """Scale every element of ``stream`` by ``factor``."""
    for value in stream:
        yield factor * value


def _merge(a: Iterator[int], b: Iterator[int]) -> Iterator[int]:
    """Merge two strictly-increasing streams, de-duplicating ties."""
    va, vb = next(a), next(b)
    while True:
        if va < vb:
            yield va
            va = next(a)
        elif va > vb:
            yield vb
            vb = next(b)
        else:  # equal -- emit once, advance both
            yield va
            va = next(a)
            vb = next(b)


def hamming() -> Iterator[int]:
    """Yield the Hamming numbers in order, lazily and forever.

    >>> list(islice(hamming(), 10))
    [1, 2, 3, 4, 5, 6, 8, 9, 10, 12]
    """

    def _generate() -> Iterator[int]:
        yield 1
        # m2, m3, m5 are bound below before this body first runs (the
        # generator is lazy), so the self-reference is well defined.
        yield from _merge(_times(2, m2), _merge(_times(3, m3), _times(5, m5)))

    m2, m3, m5, result = tee(_generate(), 4)
    return result


def first_n_hamming(n: int) -> List[int]:
    """Return the first ``n`` Hamming numbers as a list.

    >>> first_n_hamming(5)
    [1, 2, 3, 4, 5]
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    return list(islice(hamming(), n))


def hamming_up_to(limit: int) -> List[int]:
    """Return every Hamming number ``<= limit``.

    >>> hamming_up_to(12)
    [1, 2, 3, 4, 5, 6, 8, 9, 10, 12]
    """
    out: List[int] = []
    for h in hamming():
        if h > limit:
            break
        out.append(h)
    return out


def is_hamming(n: int) -> bool:
    """Return True iff ``n`` is a Hamming number (5-smooth positive int).

    >>> is_hamming(60)      # 2**2 * 3 * 5
    True
    >>> is_hamming(7)       # prime factor > 5
    False
    """
    if n < 1:
        return False
    for prime in (2, 3, 5):
        while n % prime == 0:
            n //= prime
    return n == 1
