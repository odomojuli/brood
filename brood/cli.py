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
from typing import List, Optional, Sequence, Tuple

from . import __version__
from .hamming import first_n_hamming, hamming_up_to
from .primes import factorize, sieve_atkin
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

    else:  # pragma: no cover - argparse enforces a valid command
        parser.error("unknown command")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
