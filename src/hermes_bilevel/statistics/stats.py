"""Minimal statistical helpers (stdlib only)."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def variance(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def paired_bootstrap_ci(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Return (mean_diff, lo, hi) for mean(b-a)."""
    if len(a) != len(b) or not a:
        return (0.0, 0.0, 0.0)
    diffs = [float(b[i]) - float(a[i]) for i in range(len(a))]
    rng = random.Random(seed)
    boots: list[float] = []
    n = len(diffs)
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boots.append(mean(sample))
    boots.sort()
    lo_i = int((alpha / 2) * n_boot)
    hi_i = int((1 - alpha / 2) * n_boot) - 1
    hi_i = max(0, min(hi_i, n_boot - 1))
    return (mean(diffs), boots[lo_i], boots[hi_i])


def effect_size_paired(a: Sequence[float], b: Sequence[float]) -> float:
    """Cohen's dz for paired samples."""
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    diffs = [float(b[i]) - float(a[i]) for i in range(len(a))]
    sd = math.sqrt(variance(diffs))
    if sd == 0:
        return 0.0
    return mean(diffs) / sd
