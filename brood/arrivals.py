"""Random arrival and human-delay models (the Poisson side of brood).

Two related ideas from queueing theory, distilled from the original
``poisson.ipynb``:

1. **A Poisson process.** Events that arrive memorylessly at average rate
   ``rate`` have *Exponential* inter-arrival gaps (mean ``1/rate``). This is
   the canonical model of "random but steady" traffic -- and the limit that
   the full-jitter backoff of :mod:`brood.ratelimit` approximates: jittered
   retries converge to an approximately constant call rate.

2. **Human-like delays.** Field studies put human reaction time around
   ``274 ms`` (https://humanbenchmark.com/tests/reactiontime). Drawing delays
   from ``Poisson(lambda=274)`` gives request timings that look human rather
   than metronomic -- a gentler politeness for a scraper than uniform jitter.

Everything here is pure standard library (no NumPy): a Poisson process is just
exponential gaps, and Poisson variates come from Knuth's method (small means)
or the normal approximation (large means).

See ``docs/mathematics.md`` for how this sits beside the coprime-timing tools.
"""
from __future__ import annotations

import math
import random
from typing import List, Optional

__all__ = [
    "HUMAN_REACTION_MS",
    "exponential_gaps",
    "poisson_process",
    "human_delays",
]

#: Mean human reaction time in milliseconds (humanbenchmark.com field data).
HUMAN_REACTION_MS = 274


def exponential_gaps(mean: float, n: int, seed: Optional[int] = None) -> List[float]:
    """``n`` Exponential inter-arrival gaps with the given ``mean``.

    These are the gaps of a Poisson process of rate ``1/mean``.

    >>> gaps = exponential_gaps(100.0, 5, seed=0)
    >>> len(gaps) == 5 and all(g > 0 for g in gaps)
    True
    """
    if mean <= 0:
        raise ValueError("mean must be positive")
    if n < 0:
        raise ValueError("n must be non-negative")
    rng = random.Random(seed)
    return [rng.expovariate(1.0 / mean) for _ in range(n)]


def poisson_process(rate: float, horizon: float,
                    seed: Optional[int] = None) -> List[float]:
    """Event times in ``[0, horizon)`` from a homogeneous Poisson process.

    ``rate`` is the mean number of events per unit time.

    >>> ts = poisson_process(0.01, 1000, seed=1)
    >>> ts == sorted(ts) and all(0 <= t < 1000 for t in ts)
    True
    """
    if rate <= 0:
        raise ValueError("rate must be positive")
    if horizon < 0:
        raise ValueError("horizon must be non-negative")
    rng = random.Random(seed)
    times: List[float] = []
    t = 0.0
    while True:
        t += rng.expovariate(rate)
        if t >= horizon:
            return times
        times.append(t)


def _poisson(lam: float, rng: random.Random) -> int:
    """A single Poisson(lam) variate using only the standard library."""
    if lam < 30:  # Knuth's algorithm; exp(-lam) underflows for large lam
        target = math.exp(-lam)
        k, product = 0, 1.0
        while True:
            k += 1
            product *= rng.random()
            if product <= target:
                return k - 1
    return max(0, round(rng.gauss(lam, math.sqrt(lam))))  # normal approximation


def human_delays(n: int, mean_ms: float = HUMAN_REACTION_MS,
                 seed: Optional[int] = None) -> List[int]:
    """``n`` human-like delays in milliseconds, drawn from ``Poisson(mean_ms)``.

    Useful as a "look human" alternative to uniform jitter when pacing a
    scraper.

    >>> d = human_delays(1000, seed=0)
    >>> len(d) == 1000 and all(x >= 0 for x in d)
    True
    >>> 250 < sum(d) / len(d) < 300        # clusters around ~274 ms
    True
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if mean_ms <= 0:
        raise ValueError("mean_ms must be positive")
    rng = random.Random(seed)
    return [_poisson(mean_ms, rng) for _ in range(n)]
