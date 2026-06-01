"""Prime generation via the Sieve of Atkin, plus integer factorization.

The Sieve of Atkin is a modern algorithm for enumerating primes up to a
bound using binary quadratic forms.

    A. O. L. Atkin & D. J. Bernstein (2004),
    "Prime sieves using binary quadratic forms",
    Mathematics of Computation 73 (246): 1023-1030.

In ``brood`` the primes matter because a job scheduled on a prime-length
cadence shares no common factor with the 2-, 3-, and 5-periodic jobs that
dominate ordinary schedules -- the same coprime trick periodical cicadas
use to dodge predators (see the package docstring and the README).
"""
from __future__ import annotations

import math
from typing import List

__all__ = ["sieve_atkin", "primes_up_to", "is_prime", "factorize"]


def sieve_atkin(limit: int) -> List[int]:
    """Return every prime ``p`` with ``2 <= p <= limit``.

    >>> sieve_atkin(30)
    [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    >>> sieve_atkin(1)
    []
    """
    if limit < 2:
        return []

    # is_prime[n] is toggled by the quadratic forms below; only candidates
    # of the form 6k +/- 1 (i.e. >= 5) are tracked.
    is_candidate = {n: False for n in range(5, limit + 1)}
    root = math.isqrt(limit)

    for x in range(1, root + 1):
        for y in range(1, root + 1):
            n = 4 * x * x + y * y
            if n <= limit and n % 12 in (1, 5):
                is_candidate[n] = not is_candidate[n]

            n = 3 * x * x + y * y
            if n <= limit and n % 12 == 7:
                is_candidate[n] = not is_candidate[n]

            n = 3 * x * x - y * y
            if x > y and n <= limit and n % 12 == 11:
                is_candidate[n] = not is_candidate[n]

    # Remove multiples of squares of confirmed primes.
    for n in range(5, root + 1):
        if is_candidate[n]:
            step = n * n
            for k in range(step, limit + 1, step):
                is_candidate[k] = False

    primes = [p for p in (2, 3) if p <= limit]
    primes.extend(n for n in range(5, limit + 1) if is_candidate[n])
    return primes


# Friendlier alias -- reads better at call sites and in the CLI.
def primes_up_to(limit: int) -> List[int]:
    """Alias for :func:`sieve_atkin`: all primes ``<= limit``."""
    return sieve_atkin(limit)


def is_prime(n: int) -> bool:
    """Test a single integer for primality via 6k +/- 1 trial division.

    Cheaper than building a whole sieve when you only care about one number.

    >>> is_prime(17)
    True
    >>> is_prime(221)        # 13 * 17, the cicada brood alignment
    False
    """
    if n < 2:
        return False
    if n < 4:
        return True  # 2 and 3
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def factorize(n: int) -> List[int]:
    """Return the prime factors of ``n`` (with multiplicity), ascending.

    >>> factorize(60)        # a Babylonian/Hamming number: 2^2 * 3 * 5
    [2, 2, 3, 5]
    >>> factorize(221)       # 13 * 17 -- the 221-year brood alignment
    [13, 17]
    >>> factorize(13)
    [13]
    >>> factorize(1)
    []
    """
    if n < 1:
        raise ValueError("factorize requires a positive integer")

    factors: List[int] = []
    for prime in sieve_atkin(math.isqrt(n) + 1):
        while n % prime == 0:
            factors.append(prime)
            n //= prime
    if n > 1:
        factors.append(n)
    return factors
