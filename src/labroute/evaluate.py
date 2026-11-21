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

def label_randomization_control(
    train, test, estimator_factory, n_repeats: int = 50, seed: int = 0
) -> dict:
    """Randomized-label (permutation) control.

    Fits the estimator on the real training labels and on training labels shuffled across
    records (keeping each record's reaction class), then compares Brier scores on the real test
    set. If real labels do not beat shuffled ones, the model has not learned anything beyond
    the base rate, however good the raw score looks. This matters most on high-throughput
    datasets, where uniform conditions can make scores look strong for uninformative reasons.

    Returns real_brier, shuffled_brier_mean, shuffled_brier_std, and a one-sided permutation
    p_value: the fraction of shuffles (with the +1 correction) scoring at least as well as the
    real labels.
    """
    import random
    import statistics
    from dataclasses import replace

    train, test = list(train), list(test)
    if not train or not test:
        raise ValueError("train and test must be non-empty")
    outcomes = [o.success for o in test]

    def brier_for(train_set) -> float:
        est = estimator_factory().fit(train_set)
        return brier_score([est.predict(o.reaction_key).mean for o in test], outcomes)

    real = brier_for(train)
    rng = random.Random(seed)
    labels = [o.success for o in train]
    shuffled_scores = []
    for _ in range(n_repeats):
        rng.shuffle(labels)
        shuffled_scores.append(brier_for([replace(o, success=s) for o, s in zip(train, labels)]))

    at_least_as_good = sum(1 for s in shuffled_scores if s <= real)
    return {
        "real_brier": real,
        "shuffled_brier_mean": statistics.fmean(shuffled_scores),
        "shuffled_brier_std": statistics.pstdev(shuffled_scores),
        "p_value": (at_least_as_good + 1) / (n_repeats + 1),
        "n_repeats": n_repeats,
    }
