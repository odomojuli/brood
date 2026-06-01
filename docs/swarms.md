# Swarms: decentralized coordination for many agents

The rest of `brood` desynchronizes timing *by construction* — you pick coprime
periods and phases knowing the other jobs. But the rate-limit study
([rate-limiting.md](rate-limiting.md)) found the real win is the **many-agent**
case: a fleet of workers sharing one server's goodwill, with no central
scheduler. Swarms in nature solve exactly that, and `brood.swarm` borrows their
tricks. The biology and CS sources are in
[literature.md §8](literature.md#8-swarms--collective-behaviour).

## What the swarm literature teaches

1. **Stigmergy** — ants and slime molds coordinate through traces left in a
   shared *medium* (pheromone, flux), not direct messaging. Decentralized and
   robust.
2. **Scale-invariance** — Nagpal's Kilobots and DESYNC-TDMA adjust to the
   number of *live* participants automatically, so the budget is always fully
   used and re-divided as agents come and go.
3. **Even interleaving** — the DESYNC rule (each node slides toward the
   midpoint of its phase-neighbours) converges to a perfectly even round-robin;
   it is the state a shared roster lets you compute directly.
4. **Quorum decisions** — honeybee scouts commit to a site only once a *quorum*
   accumulates: a distributed, threshold-triggered collective action.

And one caution: **synchronization is the strong attractor** — pulse-coupled
oscillators almost always *sync*. Even interleaving must be maintained
deliberately, so `brood.swarm` ships a convergence check rather than assuming it.

## The design

```python
from brood.swarm import Swarm, InMemoryMedium

swarm = Swarm(rate=2.0, medium=InMemoryMedium())   # 2 req/s shared by the fleet
with swarm.member() as me:          # join: heartbeat into the shared medium
    for url in urls:
        me.wait()                   # pace at rate / N on an even slot
        resp = fetch(url)
        if resp.status == 429:
            me.report_throttle()    # quorum of these slows the whole swarm
```

**Stigmergy — the `Medium`.** A `Medium` is a shared store of per-member records
(`seen`, `fire`, `throttle`) under a coordination key, with three operations:
`read`, `write`, `remove`. `InMemoryMedium` ships (one process / tests); a Redis
one is about ten lines:

```python
import json
class RedisMedium:                              # client = redis.Redis(decode_responses=True)
    def __init__(self, client): self.r = client
    def read(self, key):    return {m: json.loads(v) for m, v in self.r.hgetall(key).items()}
    def write(self, key, m, record): self.r.hset(key, m, json.dumps(record))
    def remove(self, key, m):        self.r.hdel(key, m)
```

**Scale-invariance.** Each member heartbeats; `live_members()` is everyone seen
within `member_ttl`. The shared budget is split across that live count, and
re-split automatically as workers join or die — no reconfiguration.

**Even interleaving.** Members sort the live roster and take evenly-spaced slots
(member at rank `r` of `N` fires at phase `r / rate`), so the *aggregate* stream
is even at `rate`:

```text
>>> three members of a Swarm(rate=2.0), at the same instant:
even slots: [0.0, 0.5, 1.0]      # 0.5 s apart  ->  aggregate 2 req/s
```

This is the stable state the decentralized DESYNC midpoint rule converges to;
`simulate_desync` shows that convergence from random starts:

```text
>>> simulate_desync(8, seed=0)
spread (std of gaps): 0.1288  ->  0.000003     # evens out
final phases: 0.098, 0.223, 0.348, ... 0.973   # ~0.125 apart (ideal gap 1/8)
```

**Quorum circuit-breaker.** Each worker that gets rate-limited calls
`report_throttle()`. When a quorum of *distinct* workers have throttled within
`backoff_window`, every member computes the same lowered rate from the shared
traces and the whole swarm slows together — recovering as the reports age out:

```text
>>> 2 of 3 members report a throttle (quorum=2) on a Swarm(rate=2.0):
effective rate -> 1.0            # halved
slots          -> [0.0, 1.0, 2.0]  # aggregate now 1 req/s
```

**AIMD circuit-breaker (`aimd=True`).** The step above is binary; set `aimd=True`
for additive-increase / multiplicative-decrease — TCP-style congestion control
over the shared budget. Each throttle multiplies the budget by `backoff_factor`
(a hard cut, deduping a burst into one); the rate then recovers *linearly* over
time, capped at the base. The cut is written to the medium, the recovery is
computed lazily on read — so it stays stigmergic, with no coordinating writer:

```text
>>> Swarm(rate=4.0, aimd=True, backoff_window=10):
report_throttle()   -> 2.0     # multiplicative decrease (x0.5)
+5 s                -> 3.0     # additive increase  (+0.2/s)
fully recovered     -> 4.0     # capped at the base
```

It makes the swarm a set of competing flows that converge to the server's actual
limit — additive-increase / multiplicative-decrease is the rule behind TCP
congestion control, provably reaching a fair, efficient allocation. "Rate
limiting is congestion control," made literal.

## Testing your own swarm

`Swarm` takes injectable `clock` and `sleep`, so an entire fleet — membership,
slotting, backoff — is unit-testable with a fake clock and no network (that is
how the examples above are produced). For multi-process use, point a
`RedisMedium` at a real Redis and the same logic coordinates across machines.

## Honesty about the limits

- Slot agreement is **eventually consistent**: members read the shared medium
  at slightly different moments, so on a real fleet the spread is *best-effort*,
  not exact — good enough to be polite, not a hard mutual-exclusion guarantee.
- It assumes a **roughly shared clock** (wall-clock via NTP is fine for
  second-scale pacing).
- The quorum circuit-breaker is a deliberately simple step (halve while a
  quorum is recent, restore after the window); a smoother AIMD is a natural
  refinement — see [literature.md](literature.md), "Threads worth pulling."
