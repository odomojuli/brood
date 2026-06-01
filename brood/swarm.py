"""Decentralized coordination for a swarm of brood agents.

The rest of `brood` desynchronizes timing *by construction* — you choose
coprime periods and phases up front. But the real win, as the rate-limit
study found, is the **many-agent** case: a fleet of workers sharing one
server's goodwill. Swarms in nature solve exactly this with no coordinator,
and this module borrows their tricks (see ``docs/swarms.md``):

* **Stigmergy** — agents coordinate through a shared medium (a trace store),
  not direct messaging, like ants via pheromone. Plug in any
  :class:`Medium` (an in-memory one ships; a Redis one is a dozen lines).
* **Scale-invariance** — membership is discovered from heartbeats, so the
  swarm splits its budget across however many workers are *live* and
  re-divides as they join or die (cf. DESYNC-TDMA, Kilobots).
* **Even interleaving** — workers take evenly-spaced slots off the shared
  roster, the stable state the DESYNC midpoint rule converges to
  (:func:`simulate_desync` demonstrates the convergence).
* **Quorum circuit-breaking** — when a quorum of workers independently hit a
  rate limit, the whole swarm slows together, like honeybee scouts reaching a
  quorum before the colony commits.

A caveat worth respecting: synchronization is the strong attractor (pulse-
coupled oscillators almost always *sync*). Even interleaving has to be
maintained deliberately; :func:`simulate_desync` and the tests check that it
actually converges rather than collapsing into a herd.

All timing entry points take an injectable ``clock`` and ``sleep`` so a whole
swarm can be unit-tested without real time or a network.
"""
from __future__ import annotations

import math
import time
import uuid
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Optional

try:  # Protocol is 3.8+, but guard for safety
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

__all__ = ["Medium", "InMemoryMedium", "Swarm", "Member", "simulate_desync"]

_MIN_RATE = 1e-6
_RATE_KEY = "__rate__"  # reserved member id holding the shared AIMD budget


# --------------------------------------------------------------------------- #
# The shared medium (stigmergy)
# --------------------------------------------------------------------------- #
class Medium(Protocol):
    """A shared store of per-member records, keyed by a coordination ``key``.

    Implement these three operations over any backend (Redis, a database, a
    file) and the swarm coordinates through it. Records are plain dicts with
    keys ``seen`` (last heartbeat), ``fire`` (last scheduled fire), and
    ``throttle`` (last rate-limit report).
    """

    def read(self, key: str) -> Dict[str, dict]: ...
    def write(self, key: str, member_id: str, record: dict) -> None: ...
    def remove(self, key: str, member_id: str) -> None: ...


class InMemoryMedium:
    """A :class:`Medium` backed by a dict — for one process or for tests.

    For a real multi-process fleet, back the same interface with Redis (a hash
    per key) or any shared store; see ``docs/swarms.md``.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, dict]] = {}

    def read(self, key: str) -> Dict[str, dict]:
        return {m: dict(r) for m, r in self._data.get(key, {}).items()}

    def write(self, key: str, member_id: str, record: dict) -> None:
        self._data.setdefault(key, {})[member_id] = dict(record)

    def remove(self, key: str, member_id: str) -> None:
        self._data.get(key, {}).pop(member_id, None)


# --------------------------------------------------------------------------- #
# The swarm and its members
# --------------------------------------------------------------------------- #
@dataclass
class Swarm:
    """A shared rate budget coordinated across many workers, no leader.

    ``rate`` is the *global* requests per second for the whole swarm; each live
    member paces at ``rate / N`` on an evenly-spaced slot.
    """

    rate: float
    medium: Medium
    key: str = "brood"
    member_ttl: float = 10.0       # a member unseen this long is dropped
    quorum: int = 2                # throttle reports needed to slow the swarm
    backoff_factor: float = 0.5    # multiplicative-decrease factor on throttle
    backoff_window: float = 30.0   # seconds a throttle report stays "recent"
    aimd: bool = False             # AIMD circuit-breaker instead of the step
    recovery_rate: Optional[float] = None  # AIMD additive increase (rate/second)
    drift: bool = False            # leaderless midpoint nudge instead of roster
    drift_alpha: float = 0.5       # nudge fraction toward the neighbour midpoint
    epoch: float = 0.0             # shared time origin for slot phases
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], object] = time.sleep

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("rate must be positive")
        if self.recovery_rate is None:
            # recover one full multiplicative cut over a backoff_window.
            self.recovery_rate = (self.rate * (1 - self.backoff_factor)
                                  ) / max(self.backoff_window, 1e-9)

    @contextmanager
    def member(self, member_id: Optional[str] = None) -> Iterator["Member"]:
        """Join the swarm for the duration of the block, then leave cleanly."""
        mid = member_id or uuid.uuid4().hex[:8]
        m = Member(self, mid)
        m.heartbeat()
        try:
            yield m
        finally:
            self.medium.remove(self.key, mid)


@dataclass
class Member:
    """One worker's handle on the swarm."""

    swarm: Swarm
    id: str
    _last_fire: float = field(default=float("-inf"))

    # --- shared-store bookkeeping ---------------------------------------- #
    def heartbeat(self, *, fire: Optional[float] = None,
                  throttle: Optional[float] = None) -> float:
        """Announce liveness (and optionally a fire/throttle), return ``now``."""
        record = self.swarm.medium.read(self.swarm.key).get(self.id, {})
        now = self.swarm.clock()
        record["seen"] = now
        if fire is not None:
            record["fire"] = fire
        if throttle is not None:
            record["throttle"] = throttle
        self.swarm.medium.write(self.swarm.key, self.id, record)
        return now

    def report_throttle(self) -> None:
        """Tell the swarm this worker was rate-limited.

        In step mode this just feeds the quorum. In AIMD mode it applies a
        multiplicative decrease to the shared budget, deduping a burst of
        near-simultaneous reports into a single cut.
        """
        now = self.heartbeat(throttle=self.swarm.clock())
        if not self.swarm.aimd:
            return
        snapshot = self.swarm.medium.read(self.swarm.key)
        rec = snapshot.get(_RATE_KEY)
        epsilon = 1.0 / self.swarm.rate            # one nominal interval
        if rec is not None and now - rec.get("at", -1e18) < epsilon:
            return                                  # already cut this instant
        current = self._aimd_rate(snapshot, now)
        cut = max(current * self.swarm.backoff_factor, _MIN_RATE)
        self.swarm.medium.write(self.swarm.key, _RATE_KEY,
                                {"budget": cut, "at": now})

    def live_members(self) -> List[str]:
        """Sorted ids of members seen within the TTL (this one included)."""
        now = self.swarm.clock()
        snapshot = self.swarm.medium.read(self.swarm.key)
        live = [m for m, r in snapshot.items()
                if not m.startswith("__")          # skip reserved entries
                and now - r.get("seen", 0.0) <= self.swarm.member_ttl]
        if self.id not in live:
            live.append(self.id)
        return sorted(live)

    def effective_rate(self) -> float:
        """The swarm's current global rate, lowered after rate-limit reports.

        Computed from the shared traces so every member agrees without a private
        rate variable (stigmergy). ``aimd=False`` (default) is a step: while a
        *quorum* of members has a recent throttle, the rate is multiplied by
        ``backoff_factor``. ``aimd=True`` is additive-increase /
        multiplicative-decrease -- a hard cut on each throttle, then a linear
        recovery -- i.e. TCP-style congestion control over the shared budget.
        """
        now = self.swarm.clock()
        snapshot = self.swarm.medium.read(self.swarm.key)
        if self.swarm.aimd:
            return self._aimd_rate(snapshot, now)
        recent = sum(
            1 for r in snapshot.values()
            if r.get("throttle") is not None
            and now - r["throttle"] <= self.swarm.backoff_window
        )
        if recent >= self.swarm.quorum:
            return max(self.swarm.rate * self.swarm.backoff_factor, _MIN_RATE)
        return self.swarm.rate

    def _aimd_rate(self, snapshot: Dict[str, dict], now: float) -> float:
        """AIMD budget: the stored value plus linear (additive) recovery since
        the last multiplicative cut, capped at the base rate."""
        rec = snapshot.get(_RATE_KEY)
        if rec is None:
            return self.swarm.rate
        recovered = rec.get("budget", self.swarm.rate) + \
            self.swarm.recovery_rate * max(0.0, now - rec.get("at", now))
        return min(self.swarm.rate, max(recovered, _MIN_RATE))

    # --- pacing ---------------------------------------------------------- #
    def _slot(self):
        """Heartbeat, then return ``(now, next slot time >= now, cycle)``."""
        now = self.heartbeat()
        live = self.live_members()
        n = len(live)
        rank = live.index(self.id)
        rate = self.effective_rate()

        cycle = n / rate            # time for all n members to fire once
        slot = rank / rate          # this member's phase within the cycle
        k = math.ceil(((now - self.swarm.epoch) - slot) / cycle)
        t = self.swarm.epoch + slot + k * cycle
        if t < now:                 # safety net for float edges
            t += cycle
        return now, t, cycle

    def next_fire(self) -> float:
        """The next tick this member should fire on its evenly-spaced slot."""
        return self._slot()[1]

    def _drift_slot(self):
        """Heartbeat, then return ``(now, next fire)`` by the leaderless midpoint
        rule -- no roster ranks, only the two nearest neighbours' last fires.

        Converges to even spacing the way :func:`simulate_desync` does, but at
        runtime and with only local information.
        """
        now = self.heartbeat()
        cycle = len(self.live_members()) / self.effective_rate()

        if self._last_fire == float("-inf"):
            # a distinct starting phase per id breaks the synchronized symmetry
            init = (zlib.crc32(self.id.encode()) / 2 ** 32) * cycle
            k = math.ceil((now - self.swarm.epoch - init) / cycle)
            return now, self.swarm.epoch + init + k * cycle

        snapshot = self.swarm.medium.read(self.swarm.key)
        others = [(snapshot[m]["fire"] - self.swarm.epoch) % cycle
                  for m in self.live_members()
                  if m != self.id and snapshot.get(m, {}).get("fire") is not None]

        target = self._last_fire + cycle
        if others:
            phase = (self._last_fire - self.swarm.epoch) % cycle
            ahead = min((o - phase) % cycle for o in others)
            behind = min((phase - o) % cycle for o in others)
            target += self.swarm.drift_alpha * (ahead - behind) / 2.0

        while target <= self._last_fire or target < now:
            target += cycle
        return now, target

    def wait(self) -> float:
        """Block until this member's next slot, then record the fire."""
        if self.swarm.drift:
            _now, target = self._drift_slot()
        else:
            _now, target, cycle = self._slot()
            while target <= self._last_fire:    # never fire the same slot twice
                target += cycle
        self.swarm.sleep(max(0.0, target - self.swarm.clock()))
        self._last_fire = target
        self.heartbeat(fire=target)
        return target


# --------------------------------------------------------------------------- #
# The decentralized-convergence demonstration (DESYNC midpoint rule)
# --------------------------------------------------------------------------- #
def simulate_desync(n: int, iterations: int = 60, alpha: float = 0.5,
                    seed: Optional[int] = None) -> dict:
    """Run the DESYNC midpoint rule on ``n`` phases and watch them even out.

    Each agent repeatedly moves to equalize its distance to its two ring
    neighbours. From random starts this converges to even spacing (gap
    ``1/n``) -- the state the roster-based slotting reaches directly, shown
    here to emerge from purely local moves.

    Returns ``{"final_phases", "spread", "ideal_gap"}`` where ``spread`` is the
    standard deviation of the gaps after each iteration (it should fall toward
    0).

    >>> result = simulate_desync(8, seed=0)
    >>> result["spread"][-1] < result["spread"][0]      # it evens out
    True
    """
    import random

    if n < 2:
        raise ValueError("n must be at least 2")
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")

    rng = random.Random(seed)
    phase = [rng.random() for _ in range(n)]

    def gap_std(ph: List[float]) -> float:
        ordered = sorted(ph)
        gaps = [(ordered[(i + 1) % n] - ordered[i]) % 1.0 for i in range(n)]
        gaps = [g if g > 0 else 1.0 for g in gaps]
        mean = sum(gaps) / n
        return math.sqrt(sum((g - mean) ** 2 for g in gaps) / n)

    spread = [gap_std(phase)]
    for _ in range(iterations):
        order = sorted(range(n), key=lambda i: phase[i])
        updated = list(phase)
        for idx in range(n):
            i = order[idx]
            behind = phase[order[idx - 1]]
            ahead = phase[order[(idx + 1) % n]]
            d_behind = (phase[i] - behind) % 1.0
            d_ahead = (ahead - phase[i]) % 1.0
            shift = alpha * (d_ahead - d_behind) / 2.0
            updated[i] = (phase[i] + shift) % 1.0
        phase = updated
        spread.append(gap_std(phase))

    return {"final_phases": sorted(phase), "spread": spread, "ideal_gap": 1.0 / n}
