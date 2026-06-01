"""Command-line interface for brood: ``python -m brood`` or ``brood ...``.

Subcommands
-----------
    brood primes  LIMIT              primes up to LIMIT (Sieve of Atkin)
    brood factor  N                  prime factorization of N
    brood hamming [COUNT]            first COUNT Hamming numbers (--up-to LIMIT)
    brood wheel   [--basis 2,3,5]    wheel spokes; --up-to N rolls the wheel;
                                     --plot draws the clock (needs brood[viz])
    brood table   N [--mod M]        N x N multiplication table
"""
from __future__ import annotations

import argparse
from itertools import islice
from typing import List, Optional, Sequence, Tuple

from . import __version__
from .hamming import first_n_hamming, hamming_up_to
from .primes import factorize, sieve_atkin
from .ratelimit import fixed_interval, jitter, safe_gaps, schedule_n, window_basis
from .schedule import Cadence, coincidence, schedule
from .tables import format_table, multiplication_table
from .wheel import coprimes_up_to, wheel, wheel_circumference


def _parse_basis(text: str) -> Tuple[int, ...]:
    """Parse a comma-separated basis like ``"2,3,5"`` into a tuple of ints."""
    try:
        basis = tuple(int(part) for part in text.split(",") if part.strip())
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid basis: {text!r}")
    if not basis:
        raise argparse.ArgumentTypeError("basis must contain at least one integer")
    return basis


def _parse_cadence(text: str) -> Cadence:
    """Parse ``"PERIOD"`` or ``"PERIOD:PHASE"`` into a Cadence."""
    parts = text.split(":")
    period = int(parts[0])
    phase = int(parts[1]) if len(parts) > 1 else 0
    return Cadence(period, phase)


def _parse_avoid(text: str):
    """Parse a comma-separated list of cadence specs into Cadence objects."""
    return [_parse_cadence(tok) for tok in text.split(",") if tok.strip()]


def _print_sequence(values: Sequence[int]) -> None:
    print(" ".join(str(v) for v in values))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brood",
        description="Number-theoretic tools for scheduling on the off-beat.",
    )
    parser.add_argument("--version", action="version",
                        version=f"brood {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_primes = sub.add_parser("primes", help="primes up to LIMIT")
    p_primes.add_argument("limit", type=int)

    p_factor = sub.add_parser("factor", help="prime factorization of N")
    p_factor.add_argument("n", type=int)

    p_hamming = sub.add_parser("hamming", help="Hamming (5-smooth) numbers")
    p_hamming.add_argument("count", type=int, nargs="?", default=20,
                           help="how many to print (default: 20)")
    p_hamming.add_argument("--up-to", type=int, default=None, metavar="LIMIT",
                           help="print every Hamming number <= LIMIT instead")

    p_wheel = sub.add_parser("wheel", help="wheel factorization / coprime slots")
    p_wheel.add_argument("--basis", type=_parse_basis, default=(2, 3, 5),
                         help="comma-separated prime basis (default: 2,3,5)")
    p_wheel.add_argument("--up-to", type=int, default=None, metavar="N",
                         help="roll the wheel: coprime residues up to N")
    p_wheel.add_argument("--plot", action="store_true",
                         help="draw the clock (requires brood[viz])")
    p_wheel.add_argument("--turns", type=int, default=3,
                         help="turns to draw when --plot (default: 3)")

    p_table = sub.add_parser("table", help="N x N multiplication table")
    p_table.add_argument("n", type=int)
    p_table.add_argument("--mod", type=int, default=None,
                         help="reduce entries modulo MOD (use a prime)")

    p_sched = sub.add_parser("schedule", help="find a collision-avoiding slot")
    p_sched.add_argument("--every", required=True,
                         help="target period; prefix ~ to search nearby (e.g. ~13)")
    p_sched.add_argument("--avoid", default="",
                         help="existing jobs, comma-separated: PERIOD or PERIOD:PHASE")
    p_sched.add_argument("--horizon", type=int, default=None,
                         help="display window in ticks (default: one coincidence cycle)")
    p_sched.add_argument("--search", type=int, default=6,
                         help="how far to search around ~target (default: 6)")

    p_coin = sub.add_parser("coincide", help="when do two cadences collide?")
    p_coin.add_argument("a", help="cadence PERIOD[:PHASE]")
    p_coin.add_argument("b", help="cadence PERIOD[:PHASE]")

    p_pace = sub.add_parser("pace", help="rate-limit-safe pacing for an unknown limit")
    p_pace.add_argument("--windows", default="1000,250,200",
                        help="assumed limit windows in ms (default: 1000,250,200)")
    p_pace.add_argument("--lo", type=int, default=200, help="min gap (default 200)")
    p_pace.add_argument("--hi", type=int, default=240, help="max gap (default 240)")
    p_pace.add_argument("--fixed", type=int, default=None, metavar="TARGET",
                        help="print the fixed coprime interval nearest TARGET")
    p_pace.add_argument("--n", type=int, default=None, metavar="N",
                        help="print a precomputed schedule of N timestamps")
    p_pace.add_argument("--seed", type=int, default=None, help="RNG seed")

    p_scrape = sub.add_parser("scrape", help="fetch URLs politely (needs brood[http])")
    p_scrape.add_argument("urls", nargs="+", help="one or more URLs")
    p_scrape.add_argument("--per-second", type=float, default=1.0,
                          help="polite request rate (default: 1.0)")
    p_scrape.add_argument("--no-robots", action="store_true",
                          help="do not consult robots.txt")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "primes":
        _print_sequence(sieve_atkin(args.limit))

    elif args.command == "factor":
        factors = factorize(args.n)
        pretty = " * ".join(str(f) for f in factors) if factors else "(empty product)"
        print(f"{args.n} = {pretty}")

    elif args.command == "hamming":
        if args.up_to is not None:
            _print_sequence(hamming_up_to(args.up_to))
        else:
            _print_sequence(first_n_hamming(args.count))

    elif args.command == "wheel":
        if args.plot:
            try:
                from .wheel import plot_wheel
            except ImportError:  # pragma: no cover - defensive
                print("plotting needs the viz extra: pip install brood[viz]")
                return 1
            try:
                plot_wheel(basis=args.basis, turns=args.turns, show=True)
            except ImportError:
                print("plotting needs the viz extra: pip install brood[viz]")
                return 1
        elif args.up_to is not None:
            _print_sequence(coprimes_up_to(args.up_to, basis=args.basis))
        else:
            circumference = wheel_circumference(args.basis)
            spokes = wheel(args.basis)
            print(f"basis={args.basis}  circumference={circumference}  "
                  f"spokes={len(spokes)}")
            _print_sequence(spokes)

    elif args.command == "table":
        print(format_table(multiplication_table(args.n, mod=args.mod)))

    elif args.command == "schedule":
        rec = schedule(args.every, avoid=_parse_avoid(args.avoid),
                       horizon=args.horizon, search=args.search)
        print(rec.explain())

    elif args.command == "coincide":
        a, b = _parse_cadence(args.a), _parse_cadence(args.b)
        co = coincidence(a, b)
        if co is None:
            print(f"{a}  vs  {b}:  never coincide")
        else:
            print(f"{a}  vs  {b}:  first at tick {co.first}, then every {co.every}")

    elif args.command == "pace":
        windows = [int(w) for w in args.windows.split(",") if w.strip()]
        basis = window_basis(windows)
        if args.fixed is not None:
            print(f"windows={windows}  basis={basis}")
            print(f"fixed coprime interval near {args.fixed}: "
                  f"{fixed_interval(windows, args.fixed)}")
        elif args.n is not None:
            times = schedule_n(args.n, windows, args.lo, args.hi, seed=args.seed)
            print(f"windows={windows}  basis={basis}  "
                  f"({len(safe_gaps(windows, args.lo, args.hi))} safe gaps "
                  f"in [{args.lo},{args.hi}])")
            print(" ".join(map(str, times)))
        else:
            pool = safe_gaps(windows, args.lo, args.hi)
            sample = list(islice(jitter(windows, args.lo, args.hi, seed=args.seed), 12))
            print(f"windows={windows}  basis={basis}")
            print(f"safe gaps in [{args.lo},{args.hi}]: {pool}")
            print("jitter sample:", " ".join(map(str, sample)))

    elif args.command == "scrape":
        from .scraper import Disallowed, PoliteScraper

        scraper = PoliteScraper(per_second=args.per_second,
                                obey_robots=not args.no_robots)
        for url in args.urls:
            try:
                resp = scraper.get(url)
                body = getattr(resp, "content", None)
                if body is None:
                    body = getattr(resp, "text", "") or ""
                print(f"{getattr(resp, 'status_code', '?'):>3}  {len(body):>9}  {url}")
            except Disallowed:
                print(f"  -  robots.txt  {url}")
            except Exception as exc:  # noqa: BLE001 - surface any client error
                print(f"err  {type(exc).__name__}: {exc}  {url}")

    else:  # pragma: no cover - argparse enforces a valid command
        parser.error("unknown command")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
