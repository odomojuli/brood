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
import time
from collections import Counter
from dataclasses import dataclass
from math import gcd
from typing import Callable, Dict, Iterator, List, Optional, Sequence

from .primes import factorize

__all__ = [
    "window_basis",
    "safe_gaps",
    "is_safe_gap",
    "jitter",
    "golden_sequence",
    "golden_jitter",
    "fixed_interval",
    "schedule_n",
    "phase_histogram",
    "phase_uniformity",
    "max_fixed_bucket",
    "max_sliding",
    "simulate",
    "conservative_gap",
    "Pacer",
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
# Low-discrepancy (golden-ratio) pacing
# --------------------------------------------------------------------------- #
GOLDEN = (5 ** 0.5 - 1) / 2  # 1/phi ~= 0.618; the "most irrational" step


def golden_sequence(n: int, start: float = 0.0) -> List[float]:
    """The additive golden-ratio low-discrepancy sequence in ``[0, 1)``.

    ``x_k = (start + k / phi) mod 1`` fills the interval more evenly than random
    (the three-distance theorem bounds its gaps to two lengths in golden ratio).

    >>> [round(x, 3) for x in golden_sequence(5)]
    [0.0, 0.618, 0.236, 0.854, 0.472]
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    return [(start + k * GOLDEN) % 1.0 for k in range(n)]


def golden_jitter(
    windows: Sequence[int],
    lo: int,
    hi: int,
    *,
    start: Optional[float] = None,
    seed: Optional[int] = None,
) -> Iterator[int]:
    """Like :func:`jitter`, but walks the golden sequence through the safe pool.

    The gaps are still coprime-safe and still look unpredictable, but the
    arrival phases spread more uniformly across every candidate window than
    uniform random jitter -- measurably so (``docs/rate-limiting.md``, the
    low-discrepancy finding). Pass a random ``start`` (or ``seed``) so many
    clients do not share one sequence.

    >>> from itertools import islice
    >>> list(islice(golden_jitter([1000, 250, 200], 210, 222), 5))
    [211, 219, 213, 221, 217]
    """
    pool = safe_gaps(windows, lo, hi)
    if not pool:
        raise ValueError("no gaps in [lo, hi] are coprime to all windows")
    if start is None:
        start = random.Random(seed).random() if seed is not None else 0.0
    x = start % 1.0
    while True:
        yield pool[int(x * len(pool)) % len(pool)]
        x = (x + GOLDEN) % 1.0


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


# --------------------------------------------------------------------------- #
# Ready-to-use client helper
# --------------------------------------------------------------------------- #
def conservative_gap(windows: Sequence[int], capacity: int = 1) -> int:
    """The mean gap that keeps you under ``capacity`` requests per window, for
    *every* assumed window -- the rate lever from docs/rate-limiting.md.

    Equals ``ceil(max(windows) / capacity)``: the largest window binds, since
    you do not know which one is real.

    >>> conservative_gap([1000, 250, 200])      # assume 1 request per window
    1000
    >>> conservative_gap([1000, 250, 200], 4)   # assume 4 per window
    250
    """
    if capacity < 1:
        raise ValueError("capacity must be >= 1")
    return -(-max(windows) // capacity)  # ceiling division


@dataclass
class Pacer:
    """Drop-in pacing for an unknown rate limit.

    Wires together the three levers from ``docs/rate-limiting.md`` plus retry
    backoff:

    1. **Rate** -- you pick the gap band ``[lo, hi]`` (see
       :func:`conservative_gap`); nothing else changes how many requests land
       in a bucket.
    2. **Phase** -- :meth:`start_delay` offers a random start offset (full
       jitter) so many clients triggered together do not stampede.
    3. **Coprime gaps** -- inter-request delays are drawn from
       :func:`safe_gaps`, spreading you across every candidate window's phases.
    4. **Backoff** -- :meth:`backoff` is full-jitter exponential backoff for
       when the server pushes back (HTTP 429 and friends).

    The scheduling methods are pure and seedable; :meth:`run` is the blocking
    wrapper, with an injectable ``sleep`` so it is testable without real time.

    >>> p = Pacer([1000, 250, 200], 200, 240, seed=0)
    >>> plan = p.plan(5)
    >>> 0 <= plan[0] < 1000                      # phase-jittered start
    True
    >>> all(is_safe_gap(b - a, [1000, 250, 200]) for a, b in zip(plan, plan[1:]))
    True
    """

    windows: Sequence[int]
    lo: int
    hi: int
    base_backoff: int = 100        # ms, the backoff at attempt 0
    max_backoff: int = 10_000      # ms, the backoff ceiling
    jitter_start: bool = True
    seed: Optional[int] = None
    low_discrepancy: bool = False  # golden-ratio gaps instead of uniform jitter

    def __post_init__(self) -> None:
        self._pool = safe_gaps(self.windows, self.lo, self.hi)
        if not self._pool:
            raise ValueError("no gaps in [lo, hi] are coprime to all windows")
        self._rng = random.Random(self.seed)
        self._golden_x = self._rng.random()
        self._max_window = max(self.windows)
        self._started = False

    # --- pure scheduling -------------------------------------------------- #
    def start_delay(self) -> int:
        """A random start offset in ``[0, max(windows))`` -- full jitter."""
        return self._rng.randrange(self._max_window)

    def next_gap(self) -> int:
        """The next coprime-safe inter-request gap.

        Golden-ratio (low-discrepancy) selection when ``low_discrepancy`` is
        set, otherwise uniform random.
        """
        if self.low_discrepancy:
            gap = self._pool[int(self._golden_x * len(self._pool)) % len(self._pool)]
            self._golden_x = (self._golden_x + GOLDEN) % 1.0
            return gap
        return self._rng.choice(self._pool)

    def plan(self, n: int, start: int = 0) -> List[int]:
        """``n`` absolute timestamps: jittered start, then coprime gaps."""
        if n <= 0:
            return []
        offset = self.start_delay() if self.jitter_start else 0
        times = [start + offset]
        for _ in range(n - 1):
            times.append(times[-1] + self.next_gap())
        return times

    def backoff(self, attempt: int) -> int:
        """Full-jitter exponential backoff: ``randint(0, min(cap, base*2**a))``.

        Marc Brooker, *Exponential Backoff And Jitter* (AWS).
        """
        ceiling = min(self.max_backoff, self.base_backoff * (2 ** attempt))
        return self._rng.randint(0, ceiling)

    # --- ready-to-use blocking wrapper ------------------------------------ #
    def run(
        self,
        fn: Callable[[], object],
        *,
        retries: int = 5,
        rate_limited: Optional[Callable[[Exception], bool]] = None,
        sleep: Callable[[float], object] = time.sleep,
    ) -> object:
        """Pace one call, retrying with backoff-and-jitter when rate-limited.

        ``fn`` is your request (a zero-argument callable).  ``rate_limited(exc)``
        returns True when an exception means "slow down" (e.g. HTTP 429).  Call
        :meth:`run` once per request -- it spaces successive calls by a safe gap
        (and the first by the start jitter).  ``sleep`` is injectable for tests.
        """
        is_limit = rate_limited or (lambda exc: False)

        if not self._started:
            self._started = True
            if self.jitter_start:
                sleep(self.start_delay())
        else:
            sleep(self.next_gap())

        attempt = 0
        while True:
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - re-raised unless rate-limited
                if is_limit(exc) and attempt < retries:
                    sleep(self.backoff(attempt))
                    attempt += 1
                    continue
                raise
