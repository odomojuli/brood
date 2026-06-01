"""Rate-limit-safe pacing for an *unknown* limit.

You are calling a service whose rate limit you do not know, but you can guess
a handful of common windows -- say ``1000``, ``250``, ``200`` ms (i.e. 1, 4,
and 5 requests per second).  The question: how should you time requests so you
never resonate with whichever window is real?

The arithmetic is friendly.  Those defaults are all 5-smooth (Hamming)
numbers -- ``1000 = 2**3 * 5**3``, ``250 = 2 * 5**3``, ``200 = 2**3 * 5**2`` --
so they share only the primes 2 and 5.  A gap coprime to *all* of them is just
a gap coprime to 10: odd and not a multiple of 5.  That is exactly the wheel
of :func:`brood.wheel.wheel` with basis ``(2, 5)`` -- spokes ``{1, 3, 7, 9}``
mod 10.  Draw request gaps from that set and each request lands on a different
phase of every candidate window.

What this does and does not buy you is the subject of ``docs/rate-limiting.md``;
the short version (see :func:`max_fixed_bucket` vs :func:`phase_histogram`):

* Against a single fixed-window *counter*, burst size is set by your **rate**,
  not by the arithmetic of your gaps.  Coprime gaps do **not** reduce it.
* Coprime gaps *do* spread you across every window's **phases** (matters for
  sliding windows and for probing) and keep independent request streams from
  **re-synchronising** into a thundering herd (the cicada result, via
  :func:`brood.schedule.coincidence`).

Units are whatever your timeline counts; the examples use milliseconds.
"""
from __future__ import annotations

import random
from collections import Counter
from math import gcd
from typing import Dict, Iterator, List, Optional, Sequence

from .primes import factorize

__all__ = [
    "window_basis",
    "safe_gaps",
    "is_safe_gap",
    "jitter",
    "fixed_interval",
    "schedule_n",
    "phase_histogram",
    "phase_uniformity",
    "max_fixed_bucket",
    "max_sliding",
    "simulate",
]


# --------------------------------------------------------------------------- #
# The safe set
# --------------------------------------------------------------------------- #
def window_basis(windows: Sequence[int]) -> List[int]:
    """Distinct primes dividing any window -- the wheel basis to avoid.

    >>> window_basis([1000, 250, 200])
    [2, 5]
    """
    primes: set = set()
    for w in windows:
        if w <= 0:
            raise ValueError("windows must be positive")
        primes.update(factorize(w))
    return sorted(primes)


def is_safe_gap(gap: int, windows: Sequence[int]) -> bool:
    """True iff ``gap`` is coprime to every window (shares no factor)."""
    return all(gcd(gap, w) == 1 for w in windows)


def safe_gaps(windows: Sequence[int], lo: int, hi: int) -> List[int]:
    """Integer gaps in ``[lo, hi]`` coprime to every window.

    These are the inter-request delays that resonate with none of the assumed
    limits.

    >>> safe_gaps([1000, 250, 200], 210, 222)
    [211, 213, 217, 219, 221]
    """
    if lo < 1:
        raise ValueError("lo must be >= 1")
    return [g for g in range(lo, hi + 1) if is_safe_gap(g, windows)]


# --------------------------------------------------------------------------- #
# Output form 1: a randomized jitter stream
# --------------------------------------------------------------------------- #
def jitter(
    windows: Sequence[int],
    lo: int,
    hi: int,
    seed: Optional[int] = None,
) -> Iterator[int]:
    """Yield random gaps drawn from :func:`safe_gaps`, forever.

    Seed for reproducibility.  Randomising (rather than a fixed period) is what
    keeps many independent clients from re-synchronising.

    >>> from itertools import islice
    >>> list(islice(jitter([1000, 250, 200], 210, 222, seed=7), 5))
    [217, 213, 219, 211, 211]
    """
    pool = safe_gaps(windows, lo, hi)
    if not pool:
        raise ValueError("no gaps in [lo, hi] are coprime to all windows")
    rng = random.Random(seed)
    while True:
        yield rng.choice(pool)


# --------------------------------------------------------------------------- #
# Output form 2: a single fixed coprime interval
# --------------------------------------------------------------------------- #
def fixed_interval(windows: Sequence[int], target: int) -> int:
    """The gap nearest ``target`` that is coprime to every window.

    Predictable and perfectly even -- but a rigid period, so not advisable when
    many clients share it (they will all resonate with each other).

    >>> fixed_interval([1000, 250, 200], 220)
    219
    """
    if target < 2:
        raise ValueError("target must be >= 2")
    for distance in range(target):
        for candidate in (target - distance, target + distance):
            if candidate >= 2 and is_safe_gap(candidate, windows):
                return candidate
    raise ValueError("no coprime interval found")  # pragma: no cover


# --------------------------------------------------------------------------- #
# Output form 3: a precomputed schedule
# --------------------------------------------------------------------------- #
def schedule_n(
    n: int,
    windows: Sequence[int],
    lo: int,
    hi: int,
    seed: Optional[int] = None,
    start: int = 0,
) -> List[int]:
    """Cumulative timestamps for ``n`` requests with safe random gaps.

    >>> schedule_n(5, [1000, 250, 200], 210, 222, seed=7)
    [0, 217, 430, 649, 860]
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return []
    gaps = jitter(windows, lo, hi, seed)
    times = [start]
    for _ in range(n - 1):
        times.append(times[-1] + next(gaps))
    return times


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def phase_histogram(times: Sequence[int], window: int, bins: int = 10) -> List[int]:
    """How requests fall across ``bins`` equal phase-slots of one window.

    A flat histogram means you cover the window uniformly; a spiky one means
    you are phase-locked.
    """
    if bins <= 0:
        raise ValueError("bins must be positive")
    counts = [0] * bins
    for t in times:
        phase = t % window
        counts[phase * bins // window] += 1
    return counts


def phase_uniformity(times: Sequence[int], window: int, bins: int = 10) -> float:
    """Peak-to-mean ratio of the phase histogram (1.0 == perfectly uniform)."""
    counts = phase_histogram(times, window, bins)
    total = sum(counts)
    if total == 0:
        return 0.0
    mean = total / bins
    return max(counts) / mean


def max_fixed_bucket(times: Sequence[int], window: int) -> int:
    """Most requests landing in any aligned bucket ``[kW, (k+1)W)``."""
    if not times:
        return 0
    counts = Counter(t // window for t in times)
    return max(counts.values())


def max_sliding(times: Sequence[int], window: int) -> int:
    """Most requests inside any half-open interval of length ``window``."""
    ordered = sorted(times)
    best = 0
    left = 0
    for right in range(len(ordered)):
        while ordered[right] - ordered[left] >= window:
            left += 1
        best = max(best, right - left + 1)
    return best


def simulate(times: Sequence[int], window: int, capacity: int) -> Dict[str, int]:
    """Run requests past a fixed-window limiter (``capacity`` per ``window``).

    Returns counts of admitted / rejected requests and the largest burst seen
    in any window.
    """
    if capacity < 1:
        raise ValueError("capacity must be >= 1")
    counts: Counter = Counter()
    admitted = rejected = 0
    for t in times:
        bucket = t // window
        if counts[bucket] < capacity:
            counts[bucket] += 1
            admitted += 1
        else:
            rejected += 1
    return {
        "admitted": admitted,
        "rejected": rejected,
        "max_burst": max(counts.values()) if counts else 0,
    }
