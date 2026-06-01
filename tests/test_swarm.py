"""Tests for brood.swarm -- decentralized coordination, fake clock, no network."""
import pytest

from brood.swarm import InMemoryMedium, Member, Swarm, simulate_desync


class Clock:
    """A controllable clock whose sleep() advances time (no real waiting)."""

    def __init__(self, t=0.0):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, delay):
        self.t += delay


def make_swarm(rate=2.0, **kwargs):
    clk = Clock()
    kwargs.setdefault("member_ttl", 100.0)
    swarm = Swarm(rate=rate, medium=InMemoryMedium(), epoch=0.0,
                  clock=clk.now, sleep=clk.sleep, **kwargs)
    return swarm, clk


def _members(swarm, *ids):
    ms = [Member(swarm, i) for i in ids]
    for m in ms:
        m.heartbeat()
    return ms


# --------------------------------------------------------------------------- #
# Medium
# --------------------------------------------------------------------------- #
def test_inmemory_medium_roundtrip():
    med = InMemoryMedium()
    med.write("k", "a", {"seen": 1.0})
    assert med.read("k") == {"a": {"seen": 1.0}}
    med.remove("k", "a")
    assert med.read("k") == {}


def test_inmemory_medium_read_is_a_copy():
    med = InMemoryMedium()
    med.write("k", "a", {"seen": 1.0})
    med.read("k")["a"]["seen"] = 999      # mutate the copy
    assert med.read("k")["a"]["seen"] == 1.0


# --------------------------------------------------------------------------- #
# Even interleaving
# --------------------------------------------------------------------------- #
def test_swarm_rejects_nonpositive_rate():
    with pytest.raises(ValueError):
        Swarm(rate=0, medium=InMemoryMedium())


def test_members_take_evenly_spaced_slots():
    swarm, _ = make_swarm(rate=3.0)
    a, b, c = _members(swarm, "a", "b", "c")
    slots = [round(m.next_fire(), 6) for m in (a, b, c)]
    assert slots == [0.0, round(1 / 3, 6), round(2 / 3, 6)]   # 1/rate apart


def test_solo_member_paces_at_full_rate():
    swarm, _ = make_swarm(rate=5.0)
    (solo,) = _members(swarm, "solo")
    fires = [round(solo.wait(), 6) for _ in range(4)]
    assert fires == [0.0, 0.2, 0.4, 0.6]      # 1/5 s apart


def test_wait_never_repeats_a_slot():
    swarm, _ = make_swarm(rate=4.0)
    (m,) = _members(swarm, "m")
    fires = [m.wait() for _ in range(5)]
    assert all(b > a for a, b in zip(fires, fires[1:]))


# --------------------------------------------------------------------------- #
# Scale-invariant membership
# --------------------------------------------------------------------------- #
def test_membership_expires_after_ttl():
    swarm, clk = make_swarm(rate=2.0, member_ttl=10.0)
    a, b, c = _members(swarm, "a", "b", "c")
    assert a.live_members() == ["a", "b", "c"]
    clk.t = 25.0                  # everyone's heartbeat is now stale
    a.heartbeat()                 # only a refreshes
    assert a.live_members() == ["a"]


def test_budget_splits_across_live_members():
    swarm, _ = make_swarm(rate=2.0)
    (solo,) = _members(swarm, "a")
    # solo: cycle = 1 / rate
    _now, _t, cycle_solo = solo._slot()
    assert cycle_solo == pytest.approx(0.5)
    _members(swarm, "b", "c")     # now three live
    _now, _t, cycle_three = solo._slot()
    assert cycle_three == pytest.approx(1.5)   # 3 / rate


# --------------------------------------------------------------------------- #
# Quorum circuit-breaker
# --------------------------------------------------------------------------- #
def test_quorum_throttle_slows_the_swarm():
    swarm, clk = make_swarm(rate=2.0, quorum=2, backoff_factor=0.5,
                            backoff_window=30.0)
    a, b, c = _members(swarm, "a", "b", "c")
    assert a.effective_rate() == 2.0          # no throttles yet
    a.report_throttle()
    assert a.effective_rate() == 2.0          # one report < quorum
    b.report_throttle()
    assert a.effective_rate() == 1.0          # quorum reached -> halved


def test_quorum_backoff_recovers_after_window():
    swarm, clk = make_swarm(rate=2.0, quorum=2, backoff_window=30.0)
    a, b, c = _members(swarm, "a", "b", "c")
    a.report_throttle()
    b.report_throttle()
    assert a.effective_rate() == 1.0
    clk.t = 40.0                              # reports age out of the window
    assert a.effective_rate() == 2.0


# --------------------------------------------------------------------------- #
# Membership lifecycle
# --------------------------------------------------------------------------- #
def test_member_context_joins_and_leaves():
    swarm, _ = make_swarm()
    with swarm.member("x") as m:
        assert m.id == "x"
        assert "x" in swarm.medium.read(swarm.key)
    assert "x" not in swarm.medium.read(swarm.key)   # cleaned up on exit


# --------------------------------------------------------------------------- #
# Decentralized convergence (the DESYNC midpoint rule)
# --------------------------------------------------------------------------- #
def test_simulate_desync_converges():
    result = simulate_desync(10, iterations=80, seed=1)
    assert result["spread"][-1] < result["spread"][0] / 10      # much more even
    assert result["spread"][-1] < 0.01
    # final gaps are close to the ideal 1/n
    phases = result["final_phases"]
    gaps = [(phases[(i + 1) % 10] - phases[i]) % 1.0 for i in range(10)]
    assert max(gaps) - min(gaps) < 0.05


def test_simulate_desync_reproducible():
    assert simulate_desync(8, seed=3) == simulate_desync(8, seed=3)


@pytest.mark.parametrize("n, alpha", [(1, 0.5), (5, 0), (5, 1.5)])
def test_simulate_desync_validation(n, alpha):
    with pytest.raises(ValueError):
        simulate_desync(n, alpha=alpha)
