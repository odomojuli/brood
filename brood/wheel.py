"""Wheel factorization -- the residues coprime to a basis of small primes.

Take the first few primes as a *basis*, e.g. ``(2, 3, 5)``.  Their product
is the wheel's *circumference* ``C = 30``.  The *spokes* are the residues in
``1..C-1`` that are coprime to ``C``::

    {1, 7, 11, 13, 17, 19, 23, 29}      (there are phi(30) = 8 of them)

Every prime greater than the largest basis prime is congruent to one of the
spokes, so "rolling the wheel" -- emitting ``C*turn + spoke`` -- enumerates
all integers that share no factor with the basis.  Sieves use this to skip
the 2-, 3-, and 5-multiples up front.

For ``brood`` the spokes have a second reading: they are exactly the offsets
that never collide with a 2-, 3-, or 5-periodic job.  A wheel is a cicada's
coprime niche drawn as a clock -- see :func:`plot_wheel`.

    https://en.wikipedia.org/wiki/Wheel_factorization
"""
from __future__ import annotations

from math import gcd, prod
from typing import List, Sequence

__all__ = [
    "wheel_circumference",
    "wheel",
    "coprimes_up_to",
    "plot_wheel",
]

DEFAULT_BASIS = (2, 3, 5)


def wheel_circumference(basis: Sequence[int] = DEFAULT_BASIS) -> int:
    """Return the wheel circumference ``C`` -- the product of the basis.

    >>> wheel_circumference((2, 3, 5))
    30
    """
    return prod(basis)


def wheel(basis: Sequence[int] = DEFAULT_BASIS) -> List[int]:
    """Return the wheel spokes: residues in ``1..C-1`` coprime to the basis.

    >>> wheel((2, 3, 5))
    [1, 7, 11, 13, 17, 19, 23, 29]
    >>> wheel((2, 3))
    [1, 5]
    """
    circumference = prod(basis)
    return [r for r in range(1, circumference) if gcd(r, circumference) == 1]


def coprimes_up_to(n: int, basis: Sequence[int] = DEFAULT_BASIS) -> List[int]:
    """Every integer in ``1..n`` coprime to the basis, by rolling the wheel.

    These are the prime candidates a wheel sieve would test -- and, in the
    scheduling reading, the slots that dodge the basis cadences.  Note that
    ``1`` is included (it is coprime to everything).

    >>> coprimes_up_to(31)
    [1, 7, 11, 13, 17, 19, 23, 29, 31]
    """
    circumference = prod(basis)
    spokes = wheel(basis)
    out: List[int] = []
    base = 0
    while base < n:
        for spoke in spokes:
            value = base + spoke
            if value > n:
                break
            out.append(value)
        base += circumference
    return out


def plot_wheel(
    basis: Sequence[int] = DEFAULT_BASIS,
    turns: int = 3,
    show: bool = False,
):
    """Draw the wheel as a clock and return the matplotlib ``Figure``.

    Integers ``1..C*turns`` are placed by residue (angle) and turn (radius).
    Spokes -- residues coprime to the basis -- are highlighted; primes get a
    ring.  Every prime lands on a spoke, which is the whole point.

    Requires the optional ``viz`` extra (``pip install brood[viz]``).  The
    import is deferred so the rest of the package stays dependency-free.
    """
    import matplotlib.pyplot as plt  # noqa: WPS433 (intentional lazy import)
    import numpy as np

    from .primes import is_prime

    circumference = prod(basis)
    spokes = set(wheel(basis))
    n = circumference * turns

    index = np.arange(1, n + 1)
    residue = index % circumference
    theta = 2 * np.pi * residue / circumference
    radius = ((index - 1) // circumference) + 1.0

    is_spoke = np.array([int(r) in spokes for r in residue])
    is_prime_mask = np.array([is_prime(int(i)) for i in index])

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    ax.scatter(theta[~is_spoke], radius[~is_spoke], s=14, c="lightgray",
               label="multiples of basis")
    ax.scatter(theta[is_spoke], radius[is_spoke], s=42, c="tab:red",
               label="spokes (coprime)")
    ax.scatter(theta[is_prime_mask], radius[is_prime_mask], s=90,
               facecolors="none", edgecolors="black", linewidths=1.2,
               label="primes")

    ax.set_yticks([])
    ax.set_xticks(np.linspace(0, 2 * np.pi, circumference, endpoint=False))
    ax.set_xticklabels(range(circumference), fontsize=7)
    ax.set_title(f"brood wheel  ·  basis={tuple(basis)}  ·  C={circumference}",
                 pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.18, 1.12), fontsize=8)
    fig.tight_layout()

    if show:
        plt.show()
    return fig
