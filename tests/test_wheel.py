"""Tests for brood.wheel -- wheel factorization and the coprime-slot view."""
from math import gcd, prod

import pytest

from brood.primes import is_prime
from brood.wheel import coprimes_up_to, wheel, wheel_circumference


def test_spokes_235():
    assert wheel((2, 3, 5)) == [1, 7, 11, 13, 17, 19, 23, 29]


def test_spoke_count_is_totient():
    # |spokes| == phi(C); for distinct primes phi(prod) == prod(p-1).
    assert len(wheel((2, 3, 5))) == (2 - 1) * (3 - 1) * (5 - 1)  # == 8


@pytest.mark.parametrize("basis, circ", [
    ((2, 3), 6), ((2, 3, 5), 30), ((2, 3, 5, 7), 210),
])
def test_circumference(basis, circ):
    assert wheel_circumference(basis) == circ


def test_spokes_are_coprime_to_basis():
    basis = (2, 3, 5)
    circ = prod(basis)
    for spoke in wheel(basis):
        assert gcd(spoke, circ) == 1


def test_wheel_23():
    assert wheel((2, 3)) == [1, 5]


def test_coprimes_roll():
    assert coprimes_up_to(31) == [1, 7, 11, 13, 17, 19, 23, 29, 31]


def test_coprimes_all_coprime():
    circ = prod((2, 3, 5))
    assert all(gcd(v, circ) == 1 for v in coprimes_up_to(200))


def test_every_prime_above_basis_is_a_slot():
    # Primes greater than the largest basis prime must all lie on the wheel.
    slots = set(coprimes_up_to(500))
    for p in range(7, 501):
        if is_prime(p):
            assert p in slots, p


def test_plot_wheel_returns_figure():
    plt = pytest.importorskip("matplotlib")
    pytest.importorskip("numpy")
    import matplotlib
    matplotlib.use("Agg")  # headless
    from brood.wheel import plot_wheel

    fig = plot_wheel(basis=(2, 3, 5), turns=2, show=False)
    # three scatter layers: non-spokes, spokes, primes
    assert len(fig.axes[0].collections) == 3
    plt_module = __import__("matplotlib.pyplot", fromlist=["close"])
    plt_module.close(fig)
