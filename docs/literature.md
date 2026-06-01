# Literature: where to find the mathematical insight

An annotated map of the ideas `brood` draws on, grouped by theme. Each entry is
the source, a one- or two-line note on the insight, and **→** how it connects to
the code. It is a reading list, not a survey: enough to chase any thread into the
primary literature.

A recurring surprise runs through it: the *same* relationship between
periods — whether they share factors — is optimised in **opposite directions**
depending on the goal. Biology and collision-avoidance want **coprime** periods
(rare coincidence); real-time scheduling often wants **harmonic** periods (small
hyperperiod, full utilisation). `brood` lives on the coprime side, but §5 is
where the tension is sharpest.

---

## 1. Periodical cicadas & the prime-period hypothesis

- **Yoshimura, J. (1997). "The evolutionary origins of periodical cicadas during ice ages." *The American Naturalist* 149(1): 112–124.**
  The foundational evolutionary argument: long, prime-numbered cycles are
  favoured because they hybridise and coincide with other cycles least often.
  **→** the thesis behind `brood` — prime periods minimise overlap.

- **Goles, E., Schulz, O., & Markus, M. (2001). "Prime number selection of cycles in a predator–prey model." *Complexity* 6(4): 33–38.** ([Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1002/cplx.1040))
  A dynamical predator–prey model in which prime-numbered prey cycles emerge as
  the evolutionarily stable strategy — primes *selected for*, not assumed.
  **→** the same "coprime survives, resonance dies" mechanic `brood.schedule`
  scores.

- **Tanaka, Y., Yoshimura, J., Simon, C., Cooley, J. R., & Tainaka, K. (2009). "Allee effect in the selection for prime-numbered cycles in periodical cicadas." *PNAS* 106(22): 8975–8979.** ([PNAS](https://www.pnas.org/doi/abs/10.1073/pnas.0900215106))
  Adds a low-density (Allee) effect: when mating success drops at low numbers,
  prime cycles are selected among 10–20-year options because they hybridise
  least. **→** why *13* and *17* specifically, not just "a big number."

- **Webb, G. F. (2001). "The prime number periodical cicada problem." *Discrete and Continuous Dynamical Systems – B* 1(3): 387–399.** ([ResearchGate](https://www.researchgate.net/publication/255644702_The_prime_number_periodical_cicada_problem))
  A cleaner mathematical treatment of why prime periods resist predator
  entrainment. **→** the lcm argument made rigorous.

## 2. Coprimality, put to work

- **Degesys, J., Rose, I., Patel, A., & Nagpal, R. (2007). "DESYNC: Self-Organizing Desynchronization and TDMA on Wireless Sensor Networks." *IPSN '07*.** ([IEEE Xplore](https://ieeexplore.ieee.org/document/4379660/) · [Harvard SSR](https://ssr.seas.harvard.edu/publications/desync-self-organizing-desynchronization-and-tdma-wireless-sensor-networks))
  *Desynchronization* as a first-class distributed primitive: nodes nudge their
  phases until periodic events interleave into a collision-free round-robin —
  cutting message loss from ~58% to <1%. The closest CS cousin of `brood`'s
  whole premise. **→** `brood.schedule` / `brood.ratelimit` do statically (by
  choosing periods/phases) what DESYNC does adaptively.

- **Vaidyanathan, P. P., & Pal, P. (2011). "Sparse Sensing With Co-Prime Samplers and Arrays." *IEEE Trans. Signal Processing* 59(2): 573–586.** ([IEEE Xplore](https://ieeexplore.ieee.org/document/5757766/))
  Two samplers at coprime rates `1/MT`, `1/NT` jointly resolve detail at the
  *finer* rate `1/MNT` — coprimality used **constructively** to beat the Nyquist
  budget (`O(MN)` degrees of freedom from `M+N` sensors). **→** the same
  CRT/lcm structure as collision recurrence, read as a feature instead of a
  hazard.

## 3. Synchronization — the thing to court or avoid

- **Mirollo, R. E., & Strogatz, S. H. (1990). "Synchronization of Pulse-Coupled Biological Oscillators." *SIAM J. Applied Mathematics* 50(6): 1645–1662.** ([JSTOR](https://www.jstor.org/stable/2101911) · [PDF](https://www.clear.rice.edu/comp551/papers/MirolloStrogatz-TemporalSynchronization-SIAM1990.pdf))
  Proves that all-to-all pulse-coupled oscillators *almost always synchronise*
  (fireflies, pacemaker cells) via "absorption" — and once synced, never part.
  **→** the failure mode `brood` designs against: the thundering herd is
  synchronisation winning. Desync is the deliberate inverse.

- **The Kuramoto model** (Y. Kuramoto, 1975; survey: Strogatz, "From Kuramoto to Crawford," *Physica D* 143 (2000): 1–20).
  The canonical model of how coupled oscillators lock phase above a coupling
  threshold. **→** background for *why* independent periodic clients drift into
  bursts unless their periods/phases are kept apart.

## 4. Equidistribution, the three-gap theorem & low-discrepancy sequences

- **Weyl, H. (1916). "Über die Gleichverteilung von Zahlen mod. Eins." *Math. Annalen* 77: 313–352.**
  The equidistribution theorem: `{kα mod 1}` is uniformly distributed iff `α` is
  irrational — the continuous parent of "a coprime step visits every residue
  evenly." **→** why coprime gaps give uniform phase coverage in
  `brood.ratelimit`.

- **The three-gap (Steinhaus) theorem** — conjectured by H. Steinhaus, first proved by Sós, Surányi, and Świerczkowski (late 1950s). ([overview](https://en.wikipedia.org/wiki/Three-gap_theorem))
  The points `{0, α, 2α, …}` on a circle leave gaps of **at most three** distinct
  lengths: a fixed step spreads about as evenly as possible at every count.
  **→** the precise sense in which a single coprime cadence "fans out" neatly.

- **Roberts, M. (2018). "The Unreasonable Effectiveness of Quasirandom Sequences."** ([extremelearning.com.au](http://extremelearning.com.au/unreasonable-effectiveness-of-quasirandom-sequences/))
  An accessible tour of low-discrepancy sequences (van der Corput, Halton,
  Sobol) and the golden-ratio additive recurrence as the most uniform 1-D
  spacing. **→** a principled alternative to uniform jitter for spreading
  requests; a natural next experiment for `brood.ratelimit`.

## 5. Real-time scheduling — harmonic vs coprime (the tension)

- **Liu, C. L., & Layland, J. W. (1973). "Scheduling Algorithms for Multiprogramming in a Hard-Real-Time Environment." *JACM* 20(1): 46–61.**
  Founds rate-monotonic scheduling and the `U ≤ n(2^{1/n}−1) ≈ 69.3%`
  utilisation bound. **→** the classical frame for periodic task timing.

- **Optimal harmonic period assignment: complexity results and approximation algorithms. *Real-Time Systems* (2018).** ([Springer](https://link.springer.com/article/10.1007/s11241-018-9304-0))
  *Harmonic* task sets (every period divides another) schedule up to **100%**
  utilisation and keep the hyperperiod `lcm` small. **→** the deliberate
  opposite of `brood`: schedulability theory courts the resonance that
  collision-avoidance flees. The right choice depends entirely on whether
  coincidence is the goal (predictability) or the hazard (contention).

## 6. Smooth numbers

- **Dijkstra, E. W. (1976). *A Discipline of Programming.* Prentice-Hall.**
  Introduces "Hamming's problem" — generate `2^i·3^j·5^k` in order — the lazy
  merge `brood.hamming` implements. **→** `brood.hamming`.

- **Granville, A. (2008). "Smooth numbers: computational number theory and beyond." In *Algorithmic Number Theory* (MSRI Publications 44).** ([PDF](https://dms.umontreal.ca/~andrew/PDF/msrire.pdf))
  The standard survey: why `y`-smooth numbers (all prime factors `≤ y`) are
  central to factoring, discrete logs, and more. **→** the broader life of the
  5-smooth numbers `brood` treats as "round time."

- **The Dickman–de Bruijn `ρ` function** — density of smooth numbers. ([overview](https://en.wikipedia.org/wiki/Dickman_function))
  Quantifies *how rare* smooth numbers become: the proportion of `x^{1/u}`-smooth
  integers up to `x` tends to `ρ(u)`. **→** how thin the "round-interval" set is,
  and thus how much room the collision-free complement leaves.

- **OEIS [A051037](https://oeis.org/A051037)** (5-smooth numbers) and **[A279622](https://oeis.org/A279622)** (a prime factor > 5, the complement). The two sequences `brood.hamming` and `brood.wheel` enumerate.

## 7. Jitter & backoff in distributed systems

- **Brooker, M. "Exponential Backoff And Jitter." *AWS Architecture Blog.*** ([AWS](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) · [Marc's blog](https://brooker.co.za/blog/2015/03/21/backoff.html))
  Adding randomness to retry backoff flattens correlated retry spikes into an
  approximately constant rate. **→** the empirical backbone of `brood.ratelimit`:
  for a herd, *phase jitter* is the lever, not period coprimality
  ([rate-limiting.md](rate-limiting.md), Finding 3).

## 8. Swarms & collective behaviour

- **Reynolds, C. W. (1987). "Flocks, Herds and Schools: A Distributed Behavioral Model." *SIGGRAPH '87*.**
  The "boids" model: three local rules (separation, alignment, cohesion) yield
  lifelike flocking — the origin of "simple local rules → global order."
  **→** the design principle behind `brood.swarm`'s per-member behaviour.

- **Vicsek, T., et al. (1995). "Novel Type of Phase Transition in a System of Self-Driven Particles." *Phys. Rev. Lett.* 75: 1226–1229.**
  The minimal physics of flocking; a sharp order/disorder transition with noise
  or density. **→** minor local changes flip global behaviour.

- **Couzin, I. D., et al. (2002). "Collective memory and spatial sorting in animal groups." *J. Theor. Biol.*** ([Consensus](https://consensus.app/papers/details/c95e349a766b52fc9d508c5ac6126819/?utm_source=claude_code))
  Simple "rules of thumb" let individuals position themselves with no global
  information; small interaction changes cause major group transitions.
  **→** why decentralized slotting can work from local views.

- **Sarfati, R., et al. (2023). "Emergent periodicity in the collective synchronous flashing of fireflies." *eLife*.** ([Consensus](https://consensus.app/papers/details/43e25191de245128a73d37fd7ef33ec9/?utm_source=claude_code))
  Rhythm emerges from a decentralized "follow-the-leader" coupling where any
  individual may lead. **→** desync uses the same local machinery, inverted.

- **Seeley, T. D., & Visscher, P. K. (2004). "Quorum sensing during nest-site selection by honeybee swarms." *Behav. Ecol. Sociobiol.*** ([Consensus](https://consensus.app/papers/details/e2cb0016ab125e129c88ece2d2f81b09/?utm_source=claude_code)) · **Visscher (2006), *Annu. Rev. Entomol.*** ([Consensus](https://consensus.app/papers/details/9ff07e4f70b0517d95af6bd67ac676d6/?utm_source=claude_code))
  A quorum threshold triggers the colony's collective commitment, leaderlessly.
  **→** `brood.swarm`'s quorum circuit-breaker.

- **Reginato, D., et al. (2024). "Bottom-up robust modelling for the foraging behaviour of *Physarum polycephalum*." *J. R. Soc. Interface*.** ([Consensus](https://consensus.app/papers/details/1dec8dc9469857fd9f4e129eb97c2dd2/?utm_source=claude_code))
  Slime-mold network formation as decentralized, stigmergic multi-agent
  computation. **→** coordinate through a shared medium, not messages.

- **Bonabeau, E., Dorigo, M., & Theraulaz, G. (1999). *Swarm Intelligence: From Natural to Artificial Systems.* Oxford University Press.** ([OUP](https://global.oup.com/academic/product/swarm-intelligence-9780195131598))
  The founding synthesis of ACO/PSO and social-insect computation. **→** useful
  context; the *optimization* branch (searching graphs/spaces) is a weaker fit
  for timing coordination than the *self-organization* branch.

- **Rubenstein, M., Cornejo, A., & Nagpal, R. (2014). "Programmable self-assembly in a thousand-robot swarm." *Science* 345: 795–799.** ([Science](https://www.science.org/doi/10.1126/science.1254295))
  A 1024-Kilobot swarm self-assembles with local sensing only, and operations
  cost the same regardless of swarm size. **→** the scale-invariance
  `brood.swarm` targets: split a budget across however many workers are live.

- See also **DESYNC** (§2), the direct CS antecedent, and **Mirollo & Strogatz /
  Kuramoto** (§3) for why synchrony — the failure mode — is the default.

  **→** realized in `brood.swarm` ([swarms.md](swarms.md)): a stigmergic
  `Medium`, scale-invariant membership, even slotting, and a quorum
  circuit-breaker.

---

## Threads worth pulling

- **Low-discrepancy pacing.** Replace uniform jitter in `brood.ratelimit` with a
  golden-ratio / van der Corput schedule and measure phase coverage (§4).
- **Adaptive desync — now in `brood.swarm`** (§8): independent clients
  coordinate phases through a shared medium at runtime, not just by
  construction. Open refinement: a smoother AIMD for the quorum
  circuit-breaker instead of the current step.
- **The harmonic/coprime dial.** Expose a single knob spanning §5's two
  regimes — harmonic for predictability, coprime for contention-avoidance —
  and let the use case choose.

*Citations were gathered and checked via web search in June 2026; follow the
links for the authoritative versions.*
