"""Evaluation utilities: calibration metrics and a route selection metric.

These support retrospective evaluation. They cannot establish improved
real-world synthesis success that requires laboratory validation.
"""

from __future__ import annotations

from typing import Sequence


def brier_score(probs: Sequence[float], outcomes: Sequence[bool]) -> float:
    if len(probs) != len(outcomes) or not probs:
        raise ValueError("probs and outcomes must be non-empty and the same length")
    return sum((p - float(o)) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def prediction_reliability_table(probs: Sequence[float], outcomes: Sequence[bool], n_bins: int = 10) -> list:
    """Per-bin (mean predicted, observed frequency, count)."""
    bins = [[] for _ in range(n_bins)]
    for p, o in zip(probs, outcomes):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, float(o)))
    table = []
    for b in bins:
        if b:
            table.append(
                (sum(p for p, _ in b) / len(b), sum(o for _, o in b) / len(b), len(b))
            )
    return table


def expected_calibration_error(
    probs: Sequence[float], outcomes: Sequence[bool], n_bins: int = 10
) -> float:
    n = len(probs)
    return sum(c / n * abs(pred - obs) for pred, obs, c in prediction_reliability_table(probs, outcomes, n_bins))


def top_k_success_ratio(ranked_ids: Sequence[str], observed: dict, k: int = 1) -> float:
    """Fraction of the top-k ranked routes that succeeded."""
    top = [rid for rid in ranked_ids[:k] if rid in observed]
    if not top:
        return float("nan")
    return sum(1 for rid in top if observed[rid]) / len(top)
