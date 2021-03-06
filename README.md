# brood
Python code, functional and imperative solutions for scheduling problems

## Time and Regular Numbers
* Number Theory: 5-smooth numbers are numbers with factors of form:
  >(2^i) * (3^j) * (5^k): where i, j, k are non-negative integers.
* Babylonian Mathematics
    > Sexagesimal numbers such as 60.
* Hamming Number
    * https://oeis.org/A051037
      > Introduced by Edsger Dijkstra in 'A Discipline of Programming'
---
## Why?
```
  Whatever the Way,
  the master of strategy does not appear fast….

  Of course, slowness is bad.

  Really skillful people never get out of time,
  and are always deliberate,
  and never appear busy.

  Miyamoto Musashi (宮本 武蔵)
  1584 – 13 June 1645
```
---
## What?

This repository is titled `brood`, inspired by the allochronic speciation exhibited in the emergent behavior of periodical cicada broods.

*Magicicada* broods in North America emerge periodically in cycles of 13 years or 17 years. Alignment occurs every 221 years, which is 13 * 17 years.

The prime number hypothesis for cicada emergence patterns suggests that predators rarely overlap with the prime numbers, 13 and 17.

---

## How?
Currently this repository contains code for:
* `hamming.py`
  * Generator for Hamming Numbers
* `atkin.py`
  * Sieve of Atkin
* `multiplication_table.py`
  * Basic multiplication table


An example of using these functions would be assigning `crontab` to distribute jobs that do not overlap with common tasks assigned at common intervals of frequency.

For instance, suppose you want to avoid collisions with scheduled tasks typically assigned on the hour during peak traffic.

It is trivial to assign a job to a time-slot that is not a Hamming Number, that is the complement of Hamming Numbers as a set:
* https://oeis.org/A279622
  > Numbers with a prime factor greater than 5

Furthermore, by definition of prime number, there is no overlap if they do not contain the number factors of concern.

---
## Whereof?

Hacker folklore prescribes randomizing or selecting a prime number to assign tasks to avoid overlap.

The motivation of this repository is to refine that perspective into a formalization of a number theoretic approach to the job schedulng problem.