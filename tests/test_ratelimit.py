"""Tests for brood.ratelimit -- pacing, analysis, and the honest findings."""
import random
from itertools import islice
from math import gcd

import pytest

from brood.ratelimit import (
    Pacer,
    conservative_gap,
    fixed_interval,
    is_safe_gap,
    jitter,
    max_fixed_bucket,
    max_sliding,
    phase_histogram,
    phase_uniformity,
    safe_gaps,
    schedule_n,
    simulate,
    window_basis,
)

WINDOWS = [1000, 250, 200]


# --------------------------------------------------------------------------- #
# The safe set
# --------------------------------------------------------------------------- #
def test_window_basis():
    assert window_basis(WINDOWS) == [2, 5]
    assert window_basis([60]) == [2, 3, 5]
    assert window_basis([7, 13]) == [7, 13]


def test_safe_gaps_exact():
    assert safe_gaps(WINDOWS, 210, 222) == [211, 213, 217, 219, 221]


def test_safe_gaps_are_coprime_and_complete():
    safe = set(safe_gaps(WINDOWS, 1, 300))
    for g in range(1, 301):
        coprime = all(gcd(g, w) == 1 for w in WINDOWS)
        assert (g in safe) == coprime


def test_is_safe_gap():
    assert is_safe_gap(221, WINDOWS)
    assert not is_safe_gap(220, WINDOWS)  # even, and a multiple of 5


# --------------------------------------------------------------------------- #
# Output forms
# --------------------------------------------------------------------------- #
def test_jitter_reproducible_and_safe():
    a = list(islice(jitter(WINDOWS, 200, 240, seed=42), 50))
    b = list(islice(jitter(WINDOWS, 200, 240, seed=42), 50))
    assert a == b
    assert all(is_safe_gap(g, WINDOWS) for g in a)


def test_jitter_empty_pool_raises():
    with pytest.raises(ValueError):
        next(jitter([2], 4, 4))  # nothing in [4, 4] is coprime to 2


def test_fixed_interval_nearest_and_coprime():
    g = fixed_interval(WINDOWS, 220)
    assert g == 219
    assert is_safe_gap(g, WINDOWS)


def test_schedule_n():
    times = schedule_n(6, WINDOWS, 200, 240, seed=1)
    assert len(times) == 6
    assert times == sorted(times) and len(set(times)) == 6
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(is_safe_gap(g, WINDOWS) for g in gaps)
    assert schedule_n(0, WINDOWS, 200, 240) == []


# --------------------------------------------------------------------------- #
# Analysis primitives
# --------------------------------------------------------------------------- #
def test_phase_histogram_counts():
    hist = phase_histogram([0, 5, 10, 15], window=20, bins=4)
    assert sum(hist) == 4
    assert hist == [1, 1, 1, 1]


def test_max_fixed_bucket():
    assert max_fixed_bucket([0, 5, 10], window=10) == 2  # 0,5 share bucket 0


def test_max_sliding():
    assert max_sliding([0, 5, 10], window=10) == 2  # [0,10) holds 0 and 5


def test_simulate_rejects_overflow():
    result = simulate([0, 1, 2, 3], window=1000, capacity=2)
    assert result["admitted"] == 2
    assert result["rejected"] == 2
    assert result["max_burst"] == 2


# --------------------------------------------------------------------------- #
# The findings (these *are* the troubleshooting, as assertions)
# --------------------------------------------------------------------------- #
def test_coprime_does_not_reduce_single_stream_burst():
    # Equal-ish rate, harmonic period vs coprime period: burst size is set by
    # the rate, so the two never differ by more than one. Coprimality buys
    # nothing here -- the central honest result.
    horizon = 100_000
    harmonic = list(range(0, horizon, 200))  # shares 2 and 5 with the windows
    coprime = list(range(0, horizon, 199))   # coprime to all windows
    for window in (200, 250, 1000):
        assert abs(max_fixed_bucket(harmonic, window)
                   - max_fixed_bucket(coprime, window)) <= 1


def test_coprime_spreads_phase_better_than_harmonic():
    # Where arithmetic *does* matter: phase coverage of a single window.
    horizon = 100_000
    harmonic = list(range(0, horizon, 200))  # period divides the 1000 window
    coprime = list(range(0, horizon, 199))
    # Harmonic period 200 lands on only a few phases of a 1000 ms window;
    # coprime 199 visits them all evenly.
    assert phase_uniformity(harmonic, 1000, bins=10) > 1.5    # spiky
    assert phase_uniformity(coprime, 1000, bins=10) < 1.2     # flat


def test_phase_jitter_scatters_the_trigger_instant():
    # All clients fire at the same trigger t=0. Coprimality cannot save that
    # shared instant -- only a random phase offset scatters it. This is the
    # textbook "jitter your backoff" result, and the honest correction to the
    # naive desync story.
    n, turns = 24, 60
    pool = safe_gaps(WINDOWS, 201, 600)[:n]
    rng = random.Random(0)

    same_phase_identical = [k * 200 for _ in range(n) for k in range(turns)]
    same_phase_coprime = [k * pool[c] for c in range(n) for k in range(turns)]
    rand_phase_identical = [rng.randint(0, 199) + k * 200
                            for _ in range(n) for k in range(turns)]

    peak = lambda ts: max_fixed_bucket(ts, 5)
    assert peak(same_phase_identical) >= n     # all pile onto t=0, 200, 400...
    assert peak(same_phase_coprime) >= n       # coprime periods do NOT help here
    assert peak(rand_phase_identical) < n // 3  # phase jitter is the real lever


def test_distinct_periods_stay_apart_after_the_trigger():
    # Away from the shared trigger instant, distinct coprime periods only ever
    # realign at their (enormous) lcm, so they stay scattered; identical
    # periods re-collide every 200 ms.
    n, turns = 20, 40
    pool = safe_gaps(WINDOWS, 201, 400)[:n]
    identical = [k * 200 for _ in range(n) for k in range(1, turns)]
    distinct = [k * pool[c] for c in range(n) for k in range(1, turns)]
    assert max_fixed_bucket(identical, 5) >= n
    assert max_fixed_bucket(distinct, 5) <= 3


def test_coprime_periods_recollide_least():
    # Where period-coprimality genuinely pays off (the cron/cicada case):
    # two long-lived jobs re-collide as rarely as their lcm allows.
    from brood.schedule import Cadence, collisions

    horizon = 50_000
    harmonic = len(collisions(Cadence(200), Cadence(200), horizon))
    coprime = len(collisions(Cadence(199), Cadence(211), horizon))  # lcm 41989
    assert harmonic > 100   # identical -> collide on every firing
    assert coprime <= 2     # coprime -> only at multiples of the lcm


# --------------------------------------------------------------------------- #
# Pacer -- the ready-to-use helper wiring the three levers together
# --------------------------------------------------------------------------- #
def test_conservative_gap():
    assert conservative_gap(WINDOWS) == 1000        # 1 per window -> 1000 ms
    assert conservative_gap(WINDOWS, 4) == 250      # 4 per window -> 250 ms
    assert conservative_gap(WINDOWS, 3) == 334      # ceil(1000 / 3)


def test_pacer_plan_jittered_start_and_safe_gaps():
    plan = Pacer(WINDOWS, 200, 240, seed=0).plan(20)
    assert len(plan) == 20 and plan == sorted(plan)
    assert 0 <= plan[0] < max(WINDOWS)              # phase-jittered start
    gaps = [b - a for a, b in zip(plan, plan[1:])]
    assert all(is_safe_gap(g, WINDOWS) for g in gaps)


def test_pacer_plan_reproducible():
    assert (Pacer(WINDOWS, 200, 240, seed=5).plan(10)
            == Pacer(WINDOWS, 200, 240, seed=5).plan(10))


def test_pacer_no_jitter_start():
    assert Pacer(WINDOWS, 200, 240, jitter_start=False, seed=0).plan(3)[0] == 0


def test_pacer_backoff_full_jitter_bounds():
    p = Pacer(WINDOWS, 200, 240, base_backoff=100, max_backoff=1000, seed=0)
    for attempt in range(8):
        ceiling = min(1000, 100 * 2 ** attempt)
        for _ in range(50):
            assert 0 <= p.backoff(attempt) <= ceiling


def test_pacer_no_safe_gaps_raises():
    with pytest.raises(ValueError):
        Pacer([2], 4, 4)  # nothing in [4,4] is coprime to 2


def test_pacer_run_paces_retries_and_succeeds():
    class RateLimited(Exception):
        pass

    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] <= 2:          # rejected twice, then succeeds
            raise RateLimited()
        return "ok"

    sleeps = []
    p = Pacer(WINDOWS, 200, 240, base_backoff=100, max_backoff=1000, seed=0)
    result = p.run(flaky,
                   rate_limited=lambda e: isinstance(e, RateLimited),
                   sleep=sleeps.append)

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 3                          # start jitter + 2 backoffs
    assert 0 <= sleeps[0] < max(WINDOWS)             # phase jitter
    assert 0 <= sleeps[1] <= 100                     # backoff(0) <= base
    assert 0 <= sleeps[2] <= 200                     # backoff(1) <= 2 * base


def test_pacer_run_spaces_successive_calls():
    p = Pacer(WINDOWS, 200, 240, seed=0)
    sleeps = []
    p.run(lambda: "a", sleep=sleeps.append)          # first -> start jitter
    p.run(lambda: "b", sleep=sleeps.append)          # second -> a safe gap
    assert 0 <= sleeps[0] < max(WINDOWS)
    assert is_safe_gap(sleeps[1], WINDOWS)


def test_pacer_run_reraises_other_errors():
    p = Pacer(WINDOWS, 200, 240, seed=0)

    def boom():
        raise KeyError("nope")

    with pytest.raises(KeyError):
        p.run(boom, rate_limited=lambda e: False, sleep=lambda s: None)
