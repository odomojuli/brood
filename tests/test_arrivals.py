"""Tests for brood.arrivals -- Poisson process and human-delay models."""
import pytest

from brood.arrivals import (
    HUMAN_REACTION_MS,
    exponential_gaps,
    human_delays,
    poisson_process,
)


def _mean(xs):
    return sum(xs) / len(xs)


# --------------------------------------------------------------------------- #
# exponential_gaps
# --------------------------------------------------------------------------- #
def test_exponential_gaps_shape_and_sign():
    gaps = exponential_gaps(100.0, 1000, seed=0)
    assert len(gaps) == 1000
    assert all(g > 0 for g in gaps)


def test_exponential_gaps_mean():
    gaps = exponential_gaps(100.0, 20000, seed=0)
    assert 95 < _mean(gaps) < 105            # mean ~ 100


def test_exponential_gaps_reproducible():
    assert exponential_gaps(50.0, 100, seed=7) == exponential_gaps(50.0, 100, seed=7)


@pytest.mark.parametrize("mean, n", [(0, 5), (-1, 5)])
def test_exponential_gaps_bad_mean(mean, n):
    with pytest.raises(ValueError):
        exponential_gaps(mean, n)


# --------------------------------------------------------------------------- #
# poisson_process
# --------------------------------------------------------------------------- #
def test_poisson_process_ordered_and_bounded():
    ts = poisson_process(0.01, 5000, seed=1)
    assert ts == sorted(ts)
    assert all(0 <= t < 5000 for t in ts)


def test_poisson_process_count_matches_rate():
    # Expected count ~ rate * horizon = 1000 (std ~ 32).
    ts = poisson_process(0.01, 100000, seed=2)
    assert 850 < len(ts) < 1150


def test_poisson_process_reproducible():
    assert poisson_process(0.02, 2000, seed=3) == poisson_process(0.02, 2000, seed=3)


# --------------------------------------------------------------------------- #
# human_delays
# --------------------------------------------------------------------------- #
def test_human_delays_defaults_to_reaction_time():
    delays = human_delays(20000, seed=0)
    assert len(delays) == 20000
    assert all(d >= 0 for d in delays)
    assert 271 < _mean(delays) < 277           # clusters around 274 ms


def test_human_delays_custom_small_mean_uses_knuth():
    delays = human_delays(20000, mean_ms=5, seed=0)   # small lambda path
    assert all(d >= 0 for d in delays)
    assert 4.5 < _mean(delays) < 5.5


def test_human_delays_reproducible():
    assert human_delays(500, seed=9) == human_delays(500, seed=9)


def test_human_reaction_constant():
    assert HUMAN_REACTION_MS == 274
