"""Scores for probability forecasts over a list of states. Lower is better for both."""
from __future__ import annotations

import math


def brier(dist: dict[str, float], outcome: str) -> float:
    """Sum over states of (forecast probability - what happened)^2. 0 is perfect, 2 is worst."""
    return sum((p - (s == outcome)) ** 2 for s, p in dist.items())


def log_score(dist: dict[str, float], outcome: str, floor: float = 1e-6) -> float:
    """-ln(probability given to what happened)."""
    return -math.log(max(dist.get(outcome, 0.0), floor))


def calibration(pairs: list[tuple[float, bool]], bins: int = 10) -> list[tuple[float, float, int]]:
    """For forecasts of one state: (mean forecast, observed share, count) per probability bin."""
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        group = [(p, hit) for p, hit in pairs if lo <= p < hi or (i == bins - 1 and p == 1.0)]
        if group:
            out.append((sum(p for p, _ in group) / len(group), sum(h for _, h in group) / len(group), len(group)))
    return out


def auc(pairs: list[tuple[float, bool]]) -> float | None:
    """Chance that a random case that happened got a higher forecast than a random one that
    didn't (ties count half). 0.5 is a coin flip, 1.0 a perfect ranking."""
    pos = sorted(p for p, hit in pairs if hit)
    neg = sorted(p for p, hit in pairs if not hit)
    if not pos or not neg:
        return None
    import bisect
    total = 0.0
    for p in pos:
        lo = bisect.bisect_left(neg, p)
        hi = bisect.bisect_right(neg, p)
        total += lo + (hi - lo) / 2
    return total / (len(pos) * len(neg))
