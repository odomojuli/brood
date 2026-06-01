"""Tests for brood.hamming -- the 5-smooth (regular) numbers, OEIS A051037."""
import pytest

from brood.hamming import first_n_hamming, hamming_up_to, is_hamming

# OEIS A051037, first 20 terms.
A051037 = [1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 16, 18, 20, 24, 25, 27, 30, 32, 36]


def test_first_n_matches_oeis():
    assert first_n_hamming(20) == A051037


def test_first_n_zero():
    assert first_n_hamming(0) == []


def test_first_n_negative_raises():
    with pytest.raises(ValueError):
        first_n_hamming(-1)


def test_up_to_matches_prefix():
    assert hamming_up_to(36) == A051037


@pytest.mark.parametrize("n, expected", [
    (1, True), (60, True), (3600, True), (86400, True),  # round time intervals
    (7, False), (14, False), (0, False), (-5, False),
])
def test_is_hamming_known(n, expected):
    assert is_hamming(n) is expected


def test_generator_self_consistent():
    # Everything the generator emits is 5-smooth...
    seq = first_n_hamming(300)
    assert all(is_hamming(h) for h in seq)
    # ...and the sequence is strictly increasing.
    assert all(a < b for a, b in zip(seq, seq[1:]))


def test_membership_agrees_with_enumeration():
    # The two definitions must agree over a dense range.
    by_predicate = [n for n in range(1, 1001) if is_hamming(n)]
    assert by_predicate == hamming_up_to(1000)
