"""Troubleshoot the rate-limit desync theory by simulation.

Runs three experiments and prints the tables used in docs/rate-limiting.md,
then writes a summary chart to docs/rate-limiting.png.

    python scripts/troubleshoot_ratelimit.py
"""
from __future__ import annotations

import random

from brood.ratelimit import (
    max_fixed_bucket,
    max_sliding,
    phase_histogram,
    phase_uniformity,
    safe_gaps,
)
from brood.schedule import Cadence, collisions

WINDOWS = [1000, 250, 200]
HORIZON = 200_000  # ms


def _stream(gap, horizon=HORIZON, start=0):
    times, t = [], start
    while t < horizon:
        times.append(t)
        t += gap()
    return times


def experiment_single_stream():
    """Burst size is rate-bound; coprimality only improves phase coverage."""
    rng = random.Random(0)
    safe = safe_gaps(WINDOWS, 196, 204)  # {197, 199, 201, 203}, mean ~200
    strategies = {
        "harmonic g=200": lambda: 200,
        "coprime g=199": lambda: 199,
        "random [196,204]": lambda: rng.randint(196, 204),
        "brood jitter": lambda: rng.choice(safe),
    }
    print("== Experiment 1: one client, ~200 ms mean gap ==")
    print(f"{'strategy':18} | {'W':>4} | {'max/bucket':>10} | "
          f"{'max/sliding':>11} | {'phase peak/mean':>15}")
    print("-" * 70)
    streams = {}
    for name, gap in strategies.items():
        times = _stream(gap)
        streams[name] = times
        for w in WINDOWS:
            print(f"{name:18} | {w:>4} | {max_fixed_bucket(times, w):>10} | "
                  f"{max_sliding(times, w):>11} | "
                  f"{phase_uniformity(times, w, bins=10):>15.2f}")
        print("-" * 70)
    return streams


def experiment_herd(n=24, turns=60):
    """Phase, not period, is what scatters a herd triggered together."""
    rng = random.Random(1)
    pool = safe_gaps(WINDOWS, 201, 600)[:n]

    def build(period_of, phase_of):
        return [phase_of(c) + k * period_of(c)
                for c in range(n) for k in range(turns)]

    strategies = {
        "identical / phase 0": build(lambda c: 200, lambda c: 0),
        "identical / phase rand": build(lambda c: 200, lambda c: rng.randint(0, 199)),
        "coprime / phase 0": build(lambda c: pool[c], lambda c: 0),
        "coprime / phase rand": build(lambda c: pool[c], lambda c: rng.randint(0, 199)),
    }
    print(f"\n== Experiment 2: {n} clients triggered together ==")
    print(f"{'strategy':24} | {'peak in any 5 ms':>16}")
    print("-" * 46)
    peaks = {}
    for name, times in strategies.items():
        peaks[name] = max_fixed_bucket(times, 5)
        print(f"{name:24} | {peaks[name]:>16}")
    return peaks


def experiment_recollision(horizon=50_000):
    """Where period-coprimality pays off: rare re-collision of two jobs."""
    pairs = {
        "harmonic (200, 200)": (Cadence(200), Cadence(200)),
        "coprime (199, 211)": (Cadence(199), Cadence(211)),
    }
    print(f"\n== Experiment 3: two jobs over {horizon} ms ==")
    print(f"{'periods':22} | {'collisions':>10}")
    print("-" * 36)
    counts = {}
    for name, (a, b) in pairs.items():
        counts[name] = len(collisions(a, b, horizon))
        print(f"{name:22} | {counts[name]:>10}")
    return counts


def make_chart(streams, herd_peaks, recollide, path="docs/rate-limiting.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.2))

    # A: phase coverage of a 1000 ms window.
    bins = 10
    harm = phase_histogram(streams["harmonic g=200"], 1000, bins)
    jit = phase_histogram(streams["brood jitter"], 1000, bins)
    x = range(bins)
    w = 0.4
    ax1.bar([i - w / 2 for i in x], harm, w, label="harmonic g=200", color="tab:gray")
    ax1.bar([i + w / 2 for i in x], jit, w, label="brood jitter", color="tab:red")
    ax1.set_title("1. Phase coverage of a 1000 ms window")
    ax1.set_xlabel("phase bin (100 ms each)")
    ax1.set_ylabel("requests")
    ax1.legend(fontsize=8)

    # B: herd peak by strategy (lower better).
    labels = ["ident\nphase0", "ident\nrand", "coprime\nphase0", "coprime\nrand"]
    vals = list(herd_peaks.values())
    colors = ["tab:gray", "tab:green", "tab:orange", "tab:red"]
    ax2.bar(labels, vals, color=colors)
    ax2.set_title("2. Herd: peak requests in any 5 ms")
    ax2.set_ylabel("peak concurrent")
    for i, v in enumerate(vals):
        ax2.text(i, v, str(v), ha="center", va="bottom", fontsize=9)

    # C: re-collisions of two jobs (log scale).
    rlabels = ["harmonic\n(200,200)", "coprime\n(199,211)"]
    rvals = list(recollide.values())
    ax3.bar(rlabels, rvals, color=["tab:gray", "tab:red"])
    ax3.set_yscale("log")
    ax3.set_title("3. Two jobs: collisions in 50,000 ms")
    ax3.set_ylabel("collisions (log)")
    for i, v in enumerate(rvals):
        ax3.text(i, v, str(v), ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    print(f"\nchart -> {path}")
    return path


if __name__ == "__main__":
    streams = experiment_single_stream()
    peaks = experiment_herd()
    recollide = experiment_recollision()
    make_chart(streams, peaks, recollide)
