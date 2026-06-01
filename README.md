# brood

*Number-theoretic tools for scheduling on the off-beat — desynchronization, from cicadas to cron to scrapers.*

![license](https://img.shields.io/badge/license-MIT-blue.svg)
![python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)

Periodical cicadas emerge on **prime** cycles so they rarely share a year with
predators. `brood` borrows the arithmetic — coprimality, the Chinese Remainder
Theorem, smooth numbers, equidistribution — to place jobs, requests, and retries
so they rarely share a *tick*. The result is a small, dependency-free Python
package (plus optional extras) that runs the same idea from number theory up
into everyday systems work.

## Contents

- [Why? / What?](#why--what) — the idea, in two epigraphs and a cicada
- [Install](#install)
- [The mathematics → computer science map](#the-mathematics--computer-science-map)
- [Modules](#modules)
- [Quickstart](#quickstart)
- [Guides](#guides): [scheduling](#scheduling-find-a-quiet-slot) ·
  [rate limiting](#pacing-against-an-unknown-rate-limit) ·
  [polite scraping](#polite-scraping)
- [Documentation](#documentation)
- [Whereof?](#whereof)
- [License](#license)

## Why? / What?

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

This repository is named `brood`, after the allochronic speciation in the
emergent behaviour of periodical cicada broods. *Magicicada* broods in North
America emerge in cycles of 13 or 17 years; two broods align only every
`13 × 17 = 221` years. The **prime-number hypothesis** holds that prime cycles
rarely overlap with predator cycles — and the same is true of any two periodic
processes, which is what makes the idea useful far from the forest floor.

## Install

```sh
git clone https://github.com/odomojuli/brood
cd brood
pip install -e .            # core — pure standard library
pip install -e '.[viz]'     # + matplotlib/numpy for the wheel clock
pip install -e '.[http]'    # + requests for PoliteScraper.get()/crawl()
pip install -e '.[test]'    # + pytest
```

Requires Python 3.8+. The core imports nothing outside the standard library.

## The mathematics → computer science map

`brood` is one idea — *desynchronization by number theory* — implemented
several ways. Each module turns a piece of mathematics into an answer to a
systems problem:

| Mathematics | Computer-science problem | Module |
| --- | --- | --- |
| 5-smooth (Hamming) numbers & their complement | avoid the "round-interval" pile-up | `hamming`, `wheel` |
| Coprimality & the Chinese Remainder Theorem | when two cadences collide, and how rarely | `schedule` |
| Euler's totient & wheel factorization | enumerate the non-colliding offsets | `wheel` |
| Equidistribution / three-distance theorem | phase coverage, jitter spreading | `ratelimit` |
| Prime gaps & the prime-period hypothesis | maximise time between coincidences | `primes` |
| Cyclic groups `(Z/pZ)*` | clean residue mixing under a prime modulus | `tables` |
| Poisson processes | memoryless / human-like arrival timing | `arrivals` |

The full derivation — with a diagram and the precise statements — is in
**[docs/mathematics.md](docs/mathematics.md)**.

## Modules

| Module | What it does |
| --- | --- |
| `brood.primes` | Sieve of Atkin prime generator (Atkin & Bernstein, 2004), a single-number `is_prime`, and `factorize`. |
| `brood.hamming` | Lazy Dijkstra generator for Hamming / 5-smooth numbers (OEIS A051037), plus an `is_hamming` test. |
| `brood.wheel` | Wheel factorization: the residues coprime to a prime basis — the slots that never collide — plus a clock visualization. |
| `brood.schedule` | Collision-avoidance scheduler: place a job near a target cadence so it avoids — or maximally rarefies — coincidences, with exact CRT analysis. |
| `brood.ratelimit` | Rate-limit-safe pacing for an *unknown* limit, the `Pacer` helper, and the analysis tools ([docs/rate-limiting.md](docs/rate-limiting.md)). |
| `brood.scraper` | `PoliteScraper`: per-host paced, robots-aware, `Retry-After`-respecting HTTP for scrapers ([docs/scraping.md](docs/scraping.md)). |
| `brood.swarm` | Decentralized coordination for a fleet: a shared rate budget split across live workers, even slotting, and a quorum circuit-breaker ([docs/swarms.md](docs/swarms.md)). |
| `brood.arrivals` | Poisson process, exponential gaps, and human-like delays (`~274 ms` reaction time). |
| `brood.tables` | Multiplication tables for checking that a prime modulus generates a cyclic group. |

Everything is importable, typed (`py.typed`), and covered by `pytest` (see
`tests/`). An exploratory Poisson notebook lives in `examples/`.

## Quickstart

```python
from brood import sieve_atkin, factorize, hamming_up_to, wheel, coprimes_up_to

sieve_atkin(30)        # [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
factorize(221)         # [13, 17]  -- the cicada brood alignment
hamming_up_to(12)      # [1, 2, 3, 4, 5, 6, 8, 9, 10, 12]
wheel((2, 3, 5))       # [1, 7, 11, 13, 17, 19, 23, 29]  -- non-colliding offsets
coprimes_up_to(60)     # every collision-free slot up to 60
```

```sh
brood primes 30            # 2 3 5 7 11 13 17 19 23 29
brood factor 221           # 221 = 13 * 17   (the cicada brood alignment)
brood hamming 10           # first 10: 1 2 3 4 5 6 8 9 10 12
brood wheel                # spokes coprime to {2,3,5}: 1 7 11 13 17 19 23 29
brood wheel --plot         # draw the wheel as a clock   (needs the viz extra)
brood table 6 --mod 7      # multiplication table mod 7
brood coincide 13 5        # first at tick 0, then every 65
brood schedule --every '~13' --avoid 5,15,30   # find a collision-free slot
brood pace --windows 1000,250,200              # safe jitter for an unknown limit
brood scrape https://example.com               # fetch politely (needs brood[http])
```

Equivalently, `python -m brood ...`.

## Guides

### Scheduling: find a quiet slot

`brood.schedule` models each existing job as a *cadence* — period `p`, phase
`f`, firing at every tick `t` with `t % p == f` — then finds a slot near a
target cadence that collides as little as possible, working two levers and
reporting the exact, horizon-free coincidence analysis via the CRT.

**Lever 1 — phase.** When the new period shares a factor with the existing ones,
you can often drop the job into the gap and *never* collide:

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

**Lever 2 — coprime drift (the cicada move).** Pin the period to 13 and a
coincidence becomes inevitable — but maximally rare, and pushed out of the busy
window by choice of phase:

```text
$ brood schedule --every 13 --avoid 5,15,30 --horizon 60

  new job : every 13, phase 8
  fires at: 8, 21, 34, 47
  collisions within horizon: 0
    vs every 5,  phase 0 : first at 60, then every 65   (coprime)
  -> soonest coincidence: tick 60; rarest guaranteed gap: 65 ticks.
```

```python
from brood import schedule, coincidence, Cadence

schedule("~13", avoid=[5, 15, 30]).collision_free   # True
coincidence(Cadence(13), Cadence(5))                # Coincidence(first=0, every=65)
coincidence(Cadence(4), Cadence(6, 3))              # None — even vs odd ticks, never meet
```

Units are abstract ticks — minutes, seconds, frames, whatever your timeline counts.

### Pacing against an unknown rate limit

`brood.ratelimit` applies the idea to rate limiting: if you can only guess a few
common windows (say 1000 / 250 / 200 ms), it paces requests with gaps coprime to
all of them. The writeup is honest about where the trick helps and where it
doesn't — single-stream burst size is set by your *rate*, not your gaps; the wins
are phase coverage and keeping clients from re-synchronizing. See
**[docs/rate-limiting.md](docs/rate-limiting.md)**.

```sh
brood pace --windows 1000,250,200          # a safe jitter sample
brood pace --windows 1000,250,200 --n 8    # a precomputed schedule
```

For a real client, `brood.ratelimit.Pacer` wires the recommendation into a
drop-in `run()` — your chosen rate, a phase-jittered start, coprime gaps, and
full-jitter backoff on 429s.

### Polite scraping

`brood.scraper.PoliteScraper` makes "be nice to their server" a one-liner:
per-host paced, jittered requests that respect `Retry-After`, back off on
429/503, and obey `robots.txt` (`Crawl-delay` included). Full guide in
**[docs/scraping.md](docs/scraping.md)**.

```python
from brood import PoliteScraper

scraper = PoliteScraper(per_second=1)        # pip install 'brood[http]'
html = scraper.get("https://example.com").text
for url, resp in scraper.crawl(urls):        # paced, robots-aware, skips Disallow
    ...
```

Or bring your own client (zero extra deps): `scraper.fetch(lambda: httpx.get(url), url)`.

## Documentation

- **[docs/mathematics.md](docs/mathematics.md)** — the number-theory → CS spine.
- **[docs/rate-limiting.md](docs/rate-limiting.md)** — formalize, apply, and
  *troubleshoot* the desync-for-rate-limits idea, with simulations.
- **[docs/scraping.md](docs/scraping.md)** — the polite-scraper guide.
- **[docs/swarms.md](docs/swarms.md)** — decentralized coordination for a fleet of agents.
- **[docs/literature.md](docs/literature.md)** — annotated bibliography:
  cicada biology, coprime scheduling, equidistribution, swarms, and desync.

## Whereof?

Hacker folklore prescribes randomizing or selecting a prime number to assign
tasks and avoid overlap. The motivation of this repository is to refine that
perspective into a formalization of a number-theoretic approach to the job
scheduling problem — and to follow it, honestly, wherever it leads.

## License

[MIT](LICENSE) © odomojuli
