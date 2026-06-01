# brood
Python code, functional and imperative solutions for scheduling problems

## Time and Regular Numbers
* Number Theory: 5-smooth numbers are numbers with factors of form:
  >(2^i) * (3^j) * (5^k): where i, j, k are non-negative integers.
* Babylonian Mathematics
  > Sexagesimal numbers such as 60.
  > > 2 * 2 * 3 * 5 = 60.
* Hamming Number
  > Introduced by Edsger Dijkstra in 'A Discipline of Programming'.
  > > https://oeis.org/A051037
* Wheel factorization:
  > Generate coprimes from initial sequence of primes.
  > > https://en.wikipedia.org/wiki/Wheel_factorization
* Poisson process
  > Model behavior of events occurring incrementally and independently.
  > > https://en.wikipedia.org/wiki/Poisson_point_process
---
## Why?
```
  Whatever the Way,
  the master of strategy does not appear fast….

  Of course, slowness is bad.

  Really skillful people never get out of time,
  and are always deliberate,
  and never appear busy.

 – Miyamoto Musashi (宮本 武蔵), 1584 – 13 June 1645
```

```
"Being early is being late."
– My Mom
```
---
## What?

This repository is titled `brood`, inspired by the allochronic speciation exhibited in the emergent behavior of periodical cicada broods.

*Magicicada* broods in North America emerge periodically in cycles of 13 years or 17 years. Alignment occurs every 221 years, which is 13 * 17 years.

The prime number hypothesis for cicada emergence patterns suggests that predators rarely overlap with the prime numbers, 13 and 17.

---

## How?

`brood` is an importable Python package with a command-line interface. The core depends only on the standard library; the clock plot and the test suite are optional extras.

```sh
pip install -e .            # core (pure standard library)
pip install -e '.[viz]'     # adds matplotlib + numpy for the wheel clock
pip install -e '.[test]'    # adds pytest
```

### The package

| Module | What it does |
| --- | --- |
| `brood.primes` | Sieve of Atkin prime generator (Atkin & Bernstein, 2004), a single-number `is_prime`, and `factorize`. |
| `brood.hamming` | Lazy Dijkstra generator for Hamming / 5-smooth numbers (OEIS A051037), plus an `is_hamming` test. |
| `brood.wheel` | Wheel factorization: the residues coprime to a prime basis — the slots that never collide — plus a clock visualization. |
| `brood.schedule` | Collision-avoidance scheduler: place a job near a target cadence so it avoids — or maximally rarefies — coincidences with existing jobs, with exact CRT coincidence analysis. |
| `brood.tables` | Multiplication tables for checking that a prime modulus generates a cyclic (abelian) group. |
| `poisson.ipynb` | Notebook: approximate human-delay responses sampled from a Poisson process. |

Everything is importable and covered by `pytest` (see `tests/`).

```python
from brood import sieve_atkin, factorize, hamming_up_to, wheel, coprimes_up_to

sieve_atkin(30)        # [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
factorize(221)         # [13, 17]  -- the cicada brood alignment
hamming_up_to(12)      # [1, 2, 3, 4, 5, 6, 8, 9, 10, 12]
wheel((2, 3, 5))       # [1, 7, 11, 13, 17, 19, 23, 29]  -- non-colliding offsets
coprimes_up_to(60)     # every collision-free slot up to 60
```

### The CLI

```sh
brood primes 30            # 2 3 5 7 11 13 17 19 23 29
brood factor 221           # 221 = 13 * 17   (the cicada brood alignment)
brood hamming 10           # first 10: 1 2 3 4 5 6 8 9 10 12
brood wheel                # spokes coprime to {2,3,5}: 1 7 11 13 17 19 23 29
brood wheel --up-to 60     # all collision-free slots up to 60
brood wheel --plot         # draw the wheel as a clock   (needs the viz extra)
brood table 6 --mod 7      # multiplication table mod 7
brood coincide 13 5        # first at tick 0, then every 65
brood schedule --every '~13' --avoid 5,15,30   # find a collision-free slot
```

Equivalently, `python -m brood ...`.

### Why this helps scheduling

Suppose you want a `crontab` job that does **not** overlap with the tasks everyone assigns on the hour during peak traffic.

The "round" intervals — 60 s, 3600 s, 86400 s — are Hamming numbers: products of 2, 3 and 5. So schedule on the *complement*, a slot whose period has a prime factor greater than 5 (OEIS A279622), which is exactly what `brood wheel` enumerates:

* https://oeis.org/A279622
  > Numbers with a prime factor greater than 5

Furthermore, by definition of a prime period, two cycles share a slot only at the least common multiple of their lengths — so coprime periods collide as rarely as a 13-year brood meets a 17-year one: once every 221 turns.

### Scheduling: find a quiet slot

`brood.schedule` turns that idea into a tool. Model each existing job as a *cadence* — period `p`, phase `f`, firing at every tick `t` with `t % p == f` — then ask for a slot near a target cadence that collides as little as possible. The recommender works two levers and reports the exact, horizon-free coincidence analysis via the Chinese Remainder Theorem.

**Lever 1 — phase.** When the new period shares a factor with the existing ones, you can often drop the job into the gap and *never* collide. Ask for "about 13" against the every-5 family and it picks a multiple of 5, offset into the empty space:

```text
$ brood schedule --every '~13' --avoid 5,15,30

  new job : every 15, phase 2
  fires at: 2, 17, 32, 47, 62, ...
  collisions within horizon: 0
    vs every 5,  phase 0 : never  (shares a factor; phase-dodged)
    vs every 15, phase 0 : never  (shares a factor; phase-dodged)
    vs every 30, phase 0 : never  (shares a factor; phase-dodged)
  -> collision-free: this slot never meets any listed job.
```

**Lever 2 — coprime drift (the cicada move).** Pin the period to 13 and it can no longer share a factor, so a coincidence is inevitable — but maximally rare, and pushed out of the busy window by choice of phase:

```text
$ brood schedule --every 13 --avoid 5,15,30 --horizon 60

  new job : every 13, phase 8
  fires at: 8, 21, 34, 47
  collisions within horizon: 0
    vs every 5,  phase 0 : first at 60, then every 65   (coprime)
    vs every 15, phase 0 : first at 60, then every 195  (coprime)
    vs every 30, phase 0 : first at 60, then every 390  (coprime)
  -> soonest coincidence: tick 60; rarest guaranteed gap: 65 ticks.
```

From Python:

```python
from brood import schedule, coincidence, Cadence

schedule("~13", avoid=[5, 15, 30]).collision_free   # True
coincidence(Cadence(13), Cadence(5))                # Coincidence(first=0, every=65)
coincidence(Cadence(4), Cadence(6, 3))              # None — even vs odd ticks, never meet
```

Units are abstract ticks — minutes, seconds, frames, whatever your timeline counts.

---
## Whereof?

Hacker folklore prescribes randomizing or selecting a prime number to assign tasks to avoid overlap.

The motivation of this repository is to refine that perspective into a formalization of a number theoretic approach to the job scheduling problem.
