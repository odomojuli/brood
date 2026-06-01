"""Tests for brood.primes -- Sieve of Atkin, primality, factorization."""
from math import prod

import pytest

from brood.primes import factorize, is_prime, primes_up_to, sieve_atkin


def _reference_primes(limit):
    """Independent trial-division oracle to check the Atkin sieve against."""
    return [n for n in range(2, limit + 1)
            if all(n % d for d in range(2, int(n ** 0.5) + 1))]


def test_small_exact():
    assert sieve_atkin(30) == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]


@pytest.mark.parametrize("limit, expected", [
    (-5, []), (0, []), (1, []), (2, [2]), (3, [2, 3]), (4, [2, 3]),
])
def test_edge_limits(limit, expected):
    assert sieve_atkin(limit) == expected


def test_matches_reference():
    assert sieve_atkin(2000) == _reference_primes(2000)


def test_primes_up_to_is_alias():
    assert primes_up_to(50) == sieve_atkin(50)


def test_is_prime_matches_sieve():
    sieve_set = set(sieve_atkin(2000))
    for n in range(0, 2001):
        assert is_prime(n) == (n in sieve_set), n


@pytest.mark.parametrize("n", [-3, 0, 1])
def test_is_prime_non_primes(n):
    assert is_prime(n) is False


def test_factorize_roundtrips():
    for n in range(1, 500):
        factors = factorize(n)
        assert all(is_prime(f) for f in factors)
        assert prod(factors) == n  # empty product is 1, matching n == 1


@pytest.mark.parametrize("n, expected", [
    (60, [2, 2, 3, 5]),     # Babylonian / Hamming number
    (221, [13, 17]),        # the 13 x 17 cicada brood alignment
    (13, [13]),
    (1, []),
])
def test_factorize_known(n, expected):
    assert factorize(n) == expected


def test_factorize_rejects_non_positive():
    with pytest.raises(ValueError):
        factorize(0)
