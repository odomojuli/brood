"""Collision-avoidance scheduling on an abstract integer timeline.

A **cadence** fires at every tick ``t`` with ``t % period == phase``: a job
that repeats every ``period`` ticks, first firing at ``phase``.  Two cadences
**coincide** when they fire on the same tick.  The Chinese Remainder Theorem
settles exactly when, for cadences ``(p1, f1)`` and ``(p2, f2)`` with
``g = gcd(p1, p2)``:

* they **never** coincide if ``(f1 - f2)`` is not divisible by ``g``;
* otherwise they first coincide at a tick found by CRT, and then once every
  ``lcm(p1, p2)`` ticks thereafter.

Two levers keep a new job out of everyone's way:

1. **Phase.**  When the new period shares a factor with an existing one you
   can often drop the job into the gap and never collide at all -- an
   even-tick job (period 4) and an odd-tick job (period 6, phase 3) never
   meet.  Zero collisions, but it relies on the other job holding its phase.
2. **Period.**  Coprime periods *must* coincide, yet only once every
   ``p1 * p2`` ticks -- the rarest collision possible, and robust to phase
   drift.  This is the cicada strategy: 13- and 17-year broods share a year
   only every 221.

:func:`find_slot` searches both levers and returns the quietest slot.  It is
not told to prefer primes; a prime period coprime to the existing load simply
*scores* best, so the folklore advice falls out of the math.

All units are abstract "ticks" -- minutes, seconds, frames, whatever you like.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from math import gcd
from typing import Iterable, List, Optional, Sequence, Tuple, Union

__all__ = [
    "Cadence",
    "Coincidence",
    "coincidence",
    "collisions",
    "busy_ticks",
    "Recommendation",
    "find_slot",
    "schedule",
]

# What a caller may hand us as an "existing job".
CadenceLike = Union["Cadence", int, Tuple[int, int]]

_INF = math.inf


def _lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


# --------------------------------------------------------------------------- #
# Cadence
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Cadence:
    """A periodic job: fires at ticks ``t`` where ``t % period == phase``."""

    period: int
    phase: int = 0

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be a positive integer")
        # Normalise the phase into [0, period).
        object.__setattr__(self, "phase", self.phase % self.period)

    def fires_within(self, horizon: int) -> List[int]:
        """Ticks this cadence fires on in the half-open window ``[0, horizon)``."""
        if horizon <= self.phase:
            return []
        return list(range(self.phase, horizon, self.period))

    def fires_at(self, tick: int) -> bool:
        """Whether the cadence fires on ``tick`` (``tick >= 0``)."""
        return tick >= 0 and tick % self.period == self.phase

    def __str__(self) -> str:
        return f"every {self.period}, phase {self.phase}"


def _as_cadence(item: CadenceLike) -> Cadence:
    if isinstance(item, Cadence):
        return item
    if isinstance(item, bool):  # guard: bool is an int subclass
        raise TypeError("a bool is not a valid cadence")
    if isinstance(item, int):
        return Cadence(item)
    if isinstance(item, (tuple, list)) and len(item) == 2:
        return Cadence(int(item[0]), int(item[1]))
    raise TypeError(f"cannot read {item!r} as a Cadence")


def _cadences(avoid: Iterable[CadenceLike]) -> List[Cadence]:
    return [_as_cadence(x) for x in avoid]


# --------------------------------------------------------------------------- #
# Coincidence (exact, horizon-free)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Coincidence:
    """When two cadences meet: ``first`` tick and the ``every`` recurrence."""

    first: int
    every: int  # == lcm(periods)


def _crt_pair(a1: int, n1: int, a2: int, n2: int) -> int:
    """Smallest non-negative ``t`` with ``t%n1 == a1`` and ``t%n2 == a2``.

    Caller must have checked ``(a1 - a2) % gcd(n1, n2) == 0`` first.
    """
    g = gcd(n1, n2)
    lcm = n1 // g * n2
    n1g, n2g = n1 // g, n2 // g
    diff = (a2 - a1) // g
    inverse = pow(n1g, -1, n2g)  # n1g and n2g are coprime, so this exists
    k = (diff * inverse) % n2g
    return (a1 + n1 * k) % lcm


def coincidence(a: Cadence, b: Cadence) -> Optional[Coincidence]:
    """First tick where ``a`` and ``b`` fire together, or ``None`` if never.

    >>> coincidence(Cadence(5), Cadence(13))      # coprime -> meet every 65
    Coincidence(first=0, every=65)
    >>> coincidence(Cadence(4), Cadence(6, 3)) is None   # even vs odd -> never
    True
    """
    g = gcd(a.period, b.period)
    if (a.phase - b.phase) % g != 0:
        return None
    first = _crt_pair(a.phase, a.period, b.phase, b.period)
    return Coincidence(first=first, every=_lcm(a.period, b.period))


def collisions(a: Cadence, b: Cadence, horizon: int) -> List[int]:
    """Ticks where ``a`` and ``b`` both fire within ``[0, horizon)``."""
    return sorted(set(a.fires_within(horizon)) & set(b.fires_within(horizon)))


def busy_ticks(avoid: Iterable[CadenceLike], horizon: int) -> set:
    """Union of all ticks the ``avoid`` cadences occupy in ``[0, horizon)``."""
    occupied: set = set()
    for cad in _cadences(avoid):
        occupied.update(cad.fires_within(horizon))
    return occupied


# --------------------------------------------------------------------------- #
# Evaluation + recommendation
# --------------------------------------------------------------------------- #
def _nearest_gap(firings: Sequence[int], busy_sorted: Sequence[int]) -> float:
    """Smallest distance from any firing to the nearest busy tick."""
    if not firings or not busy_sorted:
        return _INF
    best = _INF
    for f in firings:
        i = bisect.bisect_left(busy_sorted, f)
        candidates = []
        if i < len(busy_sorted):
            candidates.append(busy_sorted[i] - f)
        if i > 0:
            candidates.append(f - busy_sorted[i - 1])
        if candidates:
            best = min(best, min(abs(c) for c in candidates))
    return best


@dataclass
class Recommendation:
    """The chosen slot, plus exact coincidence analysis against each job."""

    cadence: Cadence
    target: int
    horizon: int
    firings: List[int]
    collisions: List[int]
    soonest_coincidence: Optional[int]
    rarest_recurrence: Optional[int]
    min_gap: float
    per_job: List[Tuple[Cadence, Optional[Coincidence]]] = field(default_factory=list)
    align: bool = False

    @property
    def collision_count(self) -> int:
        return len(self.collisions)

    @property
    def collision_free(self) -> bool:
        """True iff the slot coincides with *no* existing job, ever."""
        return all(co is None for _, co in self.per_job)

    def explain(self) -> str:
        lines = [
            "Recommendation (abstract ticks)",
            f"  new job : {self.cadence}",
            f"  target  : ~{self.target}",
            f"  horizon : {self.horizon} (display window)",
            "",
        ]
        shown = ", ".join(map(str, self.firings[:12]))
        if len(self.firings) > 12:
            shown += ", ..."
        lines.append(f"  fires at: {shown}")
        lines.append(f"  collisions within horizon: {self.collision_count}"
                     + (f"  at {self.collisions}" if self.collisions else ""))
        lines.append("")

        if not self.per_job:
            lines.append("  no existing jobs to avoid.")
            return "\n".join(lines)

        lines.append("  coincidence analysis (exact, horizon-free):")
        for job, co in self.per_job:
            if co is None:
                note = "never  (shares a factor; phase-dodged)"
            else:
                kind = "coprime" if gcd(self.cadence.period, job.period) == 1 else "shared"
                note = f"first at {co.first}, then every {co.every}  ({kind})"
            lines.append(f"    vs {str(job):<22}: {note}")

        lines.append("")
        if self.align:
            if self.collision_free:
                lines.append("  -> could not align with any listed job near the target.")
            else:
                lines.append(f"  -> aligned: locks step with the listed jobs, "
                             f"coinciding every {self.rarest_recurrence} ticks.")
        elif self.collision_free:
            lines.append("  -> collision-free: this slot never meets any listed job.")
        else:
            lines.append(f"  -> soonest coincidence: tick {self.soonest_coincidence}; "
                         f"rarest guaranteed gap: {self.rarest_recurrence} ticks.")
        return "\n".join(lines)


def _evaluate(cad: Cadence, jobs: Sequence[Cadence], horizon: int) -> Recommendation:
    per_job: List[Tuple[Cadence, Optional[Coincidence]]] = []
    recurrences: List[int] = []
    soonests: List[int] = []
    for job in jobs:
        co = coincidence(cad, job)
        per_job.append((job, co))
        if co is not None:
            recurrences.append(co.every)
            soonests.append(co.first)

    firings = cad.fires_within(horizon)
    busy_sorted = sorted(busy_ticks(jobs, horizon))
    busy_set = set(busy_sorted)
    coll = sorted(t for t in firings if t in busy_set)

    return Recommendation(
        cadence=cad,
        target=cad.period,
        horizon=horizon,
        firings=firings,
        collisions=coll,
        soonest_coincidence=min(soonests) if soonests else None,
        rarest_recurrence=min(recurrences) if recurrences else None,
        min_gap=_nearest_gap(firings, busy_sorted),
        per_job=per_job,
    )


def _score(rec: Recommendation, target: int, align: bool = False) -> tuple:
    """Sort key, ascending = better.

    ``align=False`` (avoid): meet the fewest jobs, stay near the target, then
    push coincidences as rare and as late as possible and sit in the roomiest
    gap. ``align=True`` (harmonic): the mirror image -- meet as *many* jobs as
    possible, as *frequently* (small lcm) and as *soon* as possible.
    """
    meets = sum(1 for _, co in rec.per_job if co is not None)
    rarity = rec.rarest_recurrence if rec.rarest_recurrence is not None else _INF
    soonest = rec.soonest_coincidence if rec.soonest_coincidence is not None else _INF
    if align:
        # alignment quality = fraction of this job's firings that land on an
        # existing mark; then nearest to target, then most frequent (small lcm).
        quality = len(rec.collisions) / len(rec.firings) if rec.firings else 0.0
        return (
            -quality,
            abs(rec.cadence.period - target),
            rarity,
            rec.cadence.period,
            rec.cadence.phase,
        )
    return (
        meets,
        abs(rec.cadence.period - target),
        -rarity,
        -soonest,
        -rec.min_gap,
        rec.cadence.period,
        rec.cadence.phase,
    )


def _default_horizon(period: int, jobs: Sequence[Cadence], cap: int = 100_000) -> int:
    """A display window wide enough to show at least one coincidence cycle."""
    horizon = period
    for job in jobs:
        horizon = _lcm(horizon, job.period)
        if horizon >= cap:
            return cap
    return max(horizon, 2 * period)


def find_slot(
    avoid: Iterable[CadenceLike] = (),
    *,
    period: Optional[int] = None,
    approx: Optional[int] = None,
    horizon: Optional[int] = None,
    search: int = 6,
    align: bool = False,
) -> Recommendation:
    """Find a cadence near a target relative to the ``avoid`` jobs.

    Provide exactly one of ``period`` (use this exact period, search only the
    phase) or ``approx`` (search nearby periods too, ``+/- search``).

    ``align=False`` (default) finds the *quietest* slot -- it avoids or
    maximally rarefies coincidences. ``align=True`` flips the dial to
    *harmonic*: it locks step with the existing jobs, coinciding as cleanly and
    as frequently as possible (small hyperperiod) -- for when you *want* tasks
    to line up. See docs/mathematics.md §2 and docs/literature.md §5.
    """
    if (period is None) == (approx is None):
        raise ValueError("pass exactly one of period= or approx=")

    jobs = _cadences(avoid)
    target = period if period is not None else int(approx)

    if period is not None:
        candidate_periods: List[int] = [period]
    else:
        lo = max(2, target - search)
        candidate_periods = list(range(lo, target + search + 1))

    window = horizon if horizon is not None else _default_horizon(target, jobs)

    best: Optional[Recommendation] = None
    best_key: Optional[tuple] = None
    for p in candidate_periods:
        for phase in range(p):
            rec = _evaluate(Cadence(p, phase), jobs, window)
            key = _score(rec, target, align)
            if best_key is None or key < best_key:
                best_key, best = key, rec
    assert best is not None  # candidate_periods is non-empty
    # Record the original target (so a phase-only search still reports ~target).
    best.target = target
    best.align = align
    return best


def schedule(
    every: Union[int, str],
    avoid: Iterable[CadenceLike] = (),
    horizon: Optional[int] = None,
    search: int = 6,
    align: bool = False,
) -> Recommendation:
    """Friendly wrapper around :func:`find_slot`.

    ``every`` may be an int (an exact period), a string like ``"13"`` (exact),
    or ``"~13"`` (approximate -- search nearby periods). ``align`` is the
    harmonic/coprime dial: ``False`` avoids the existing jobs, ``True`` locks
    step with them.

    >>> schedule("~13", avoid=[5, 15, 30]).collision_free          # avoid: dodge them
    True
    >>> str(schedule("~13", avoid=[5, 15, 30], align=True).cadence)  # harmonic: line up
    'every 15, phase 0'
    """
    approx = False
    if isinstance(every, str):
        text = every.strip()
        if text.startswith("~"):
            approx, text = True, text[1:].strip()
        value = int(text)
    else:
        value = int(every)

    if approx:
        return find_slot(avoid, approx=value, horizon=horizon,
                         search=search, align=align)
    return find_slot(avoid, period=value, horizon=horizon,
                     search=search, align=align)
