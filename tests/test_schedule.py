"""Tests for brood.schedule -- the collision-avoidance scheduler."""
from math import gcd

import pytest

from brood.schedule import (
    Cadence,
    Coincidence,
    busy_ticks,
    coincidence,
    collisions,
    find_slot,
    schedule,
)


# --------------------------------------------------------------------------- #
# Cadence
# --------------------------------------------------------------------------- #
def test_phase_is_normalized():
    assert Cadence(5, 7).phase == 2
    assert Cadence(5, -1).phase == 4


def test_period_must_be_positive():
    with pytest.raises(ValueError):
        Cadence(0)


def test_fires_within_half_open():
    assert Cadence(13, 8).fires_within(60) == [8, 21, 34, 47]
    assert Cadence(5).fires_within(5) == [0]  # half-open: 5 excluded


def test_fires_at():
    c = Cadence(13, 8)
    assert c.fires_at(21) is True
    assert c.fires_at(22) is False


# --------------------------------------------------------------------------- #
# Coincidence -- exact CRT, cross-checked against brute force
# --------------------------------------------------------------------------- #
def test_coprime_always_meet_at_lcm():
    assert coincidence(Cadence(5), Cadence(13)) == Coincidence(first=0, every=65)


def test_shared_factor_offset_never_meet():
    # even-tick job vs odd-tick job
    assert coincidence(Cadence(4), Cadence(6, 3)) is None


def test_shared_factor_aligned_meet():
    assert coincidence(Cadence(4), Cadence(6)) == Coincidence(first=0, every=12)


def _brute_force(a: Cadence, b: Cadence):
    period = a.period // gcd(a.period, b.period) * b.period
    for t in range(period):
        if a.fires_at(t) and b.fires_at(t):
            return Coincidence(first=t, every=period)
    return None


@pytest.mark.parametrize("p1", range(2, 13))
@pytest.mark.parametrize("p2", range(2, 13))
def test_coincidence_matches_brute_force(p1, p2):
    for ph1 in range(p1):
        for ph2 in range(p2):
            a, b = Cadence(p1, ph1), Cadence(p2, ph2)
            assert coincidence(a, b) == _brute_force(a, b), (a, b)


def test_collisions_window():
    assert collisions(Cadence(6), Cadence(10), 60) == [0, 30]


def test_busy_ticks_union():
    assert busy_ticks([15, 30], 60) == {0, 15, 30, 45}


# --------------------------------------------------------------------------- #
# find_slot / schedule
# --------------------------------------------------------------------------- #
def test_phase_dodge_zero_collisions():
    # A second every-2 job can live on the odd ticks and never collide.
    rec = find_slot(avoid=[2], period=2)
    assert rec.cadence.phase == 1
    assert rec.collision_free


def test_resonant_avoidance_near_target():
    # Everything here is a multiple of 5, so a multiple-of-5 period can slot
    # into the gap and avoid them all forever.
    rec = find_slot(avoid=[5, 15, 30], approx=13)
    assert rec.collision_free
    assert rec.cadence.period % 5 == 0
    # and it really shares no firing with the busy set
    assert rec.collisions == []


def test_coprime_drift_when_unavoidable():
    # 13 is coprime to both 7 and 11, so coincidences are inevitable -- but
    # the rarest one is lcm(13, 7) = 91.
    rec = find_slot(avoid=[7, 11], period=13)
    assert not rec.collision_free
    assert rec.rarest_recurrence == 91


def test_fixed_period_dodges_inside_window():
    # period 13 vs the every-5 family: zero collisions inside [0, 60),
    # because the first true coincidence sits exactly on tick 60.
    rec = find_slot(avoid=[5, 15, 30], period=13, horizon=60)
    assert rec.collision_count == 0
    assert all(t % 5 != 0 for t in rec.firings)
    assert rec.soonest_coincidence == 60


def test_schedule_exact_vs_approx():
    exact = schedule("13", avoid=[5, 15, 30])      # forced onto 13 -> coprime
    approx = schedule("~13", avoid=[5, 15, 30])    # free to pick the period
    assert not exact.collision_free
    assert approx.collision_free


def test_find_slot_requires_one_target():
    with pytest.raises(ValueError):
        find_slot(avoid=[2])  # neither period nor approx
    with pytest.raises(ValueError):
        find_slot(avoid=[2], period=3, approx=3)  # both


def test_explain_is_stringy():
    text = schedule("~13", avoid=[5, 15, 30]).explain()
    assert "Recommendation" in text
    assert "coincidence analysis" in text


# --------------------------------------------------------------------------- #
# The harmonic/coprime dial
# --------------------------------------------------------------------------- #
def test_align_locks_step():
    rec = schedule("~13", avoid=[5, 15, 30], align=True)
    assert rec.align is True
    assert not rec.collision_free
    assert rec.cadence.period % 5 == 0          # shares the dominant factor
    assert rec.cadence.phase == 0               # lands on the marks
    assert rec.collision_count == len(rec.firings)   # every firing aligns


def test_dial_is_the_phase():
    # Same period either way near ~13 against the every-5 family; the dial just
    # flips the phase: avoid dodges into the gap, align lands on the marks.
    avoid = schedule("~13", avoid=[5, 15, 30])
    align = schedule("~13", avoid=[5, 15, 30], align=True)
    assert avoid.cadence.period == align.cadence.period == 15
    assert avoid.collision_free and not align.collision_free


def test_align_explain_mentions_lock_step():
    text = schedule("~13", avoid=[5, 15, 30], align=True).explain()
    assert "aligned" in text and "locks step" in text
