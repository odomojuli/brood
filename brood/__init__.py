"""brood -- number-theoretic tools for scheduling on the off-beat.

Periodical cicadas (*Magicicada*) emerge on 13- and 17-year cycles. Because
those periods are prime, a brood rarely shares a year with predators or with
other broods -- alignment between a 13- and a 17-year cycle happens only
every 13 * 17 = 221 years. ``brood`` borrows the trick for schedulers:
choose cadences and offsets that are *coprime* to everyone else's so your
jobs seldom collide.

The pieces:

* :mod:`brood.primes`  -- Sieve of Atkin, primality test, factorization.
* :mod:`brood.hamming` -- the 5-smooth "common interval" numbers (the beat
  you usually want to avoid) and their membership test.
* :mod:`brood.wheel`   -- wheel factorization: the residues coprime to a
  small-prime basis (the slots that never collide), plus a clock plot.
* :mod:`brood.tables`  -- multiplication tables for eyeballing group
  structure under a chosen modulus.

A command-line interface lives in :mod:`brood.cli` (``python -m brood``).
"""
from __future__ import annotations

from .hamming import first_n_hamming, hamming, hamming_up_to, is_hamming
from .primes import factorize, is_prime, primes_up_to, sieve_atkin
from .schedule import (
    Cadence,
    Coincidence,
    Recommendation,
    busy_ticks,
    coincidence,
    collisions,
    find_slot,
    schedule,
)
from .tables import format_table, multiplication_table
from .wheel import coprimes_up_to, plot_wheel, wheel, wheel_circumference

__version__ = "0.1.0"

__all__ = [
    # primes
    "sieve_atkin",
    "primes_up_to",
    "is_prime",
    "factorize",
    # hamming
    "hamming",
    "first_n_hamming",
    "hamming_up_to",
    "is_hamming",
    # wheel
    "wheel",
    "wheel_circumference",
    "coprimes_up_to",
    "plot_wheel",
    # scheduling
    "Cadence",
    "Coincidence",
    "coincidence",
    "collisions",
    "busy_ticks",
    "Recommendation",
    "find_slot",
    "schedule",
    # tables
    "multiplication_table",
    "format_table",
    "__version__",
]
