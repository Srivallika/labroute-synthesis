"""Laboratory-adaptive success estimation with explicit uncertainty.

A baseline Beta-Binomial estimator per reaction class for Phase-4 (calibrated, laboratory-adaptive success estimates).
ML models can later replace it behind the same ``predict`` interface.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import Outcome


@dataclass(frozen=True)
class Prediction:
    mean: float  # estimated probability of success
    std: float  # uncertainty of the estimate
    lower: float  # approximate 90% interval using normal approximation and clipped to [0, 1]
    upper: float
    n_effective: float  # weighted number of supporting outcomes
    sufficient_evidence: bool  # if False, treat as unknown, not as a confident estimate


class BetaSuccessEstimator:
    def __init__(
        self,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        public_weight: float = 0.3,
        min_evidence: float = 3.0,
    ):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.public_weight = public_weight
        self.min_evidence = min_evidence
        self._succ: dict = defaultdict(float)
        self._fail: dict = defaultdict(float)

    def fit(self, outcomes: Iterable[Outcome]) -> "BetaSuccessEstimator":
        self._succ.clear()
        self._fail.clear()
        for o in outcomes:
            w = 1.0 if o.source == "lab" else self.public_weight
            if o.success:
                self._succ[o.reaction_key] += w
            else:
                self._fail[o.reaction_key] += w
        return self

    def predict(self, reaction_key: str) -> Prediction:
        s, f = self._succ.get(reaction_key, 0.0), self._fail.get(reaction_key, 0.0)
        a, b = self.prior_alpha + s, self.prior_beta + f
        total = a + b
        mean = a / total
        var = (a * b) / (total**2 * (total + 1))
        std = var**0.5
        z = 1.645  # ~90% interval under a normal approximation
        lower, upper = max(0.0, mean - z * std), min(1.0, mean + z * std)
        n = s + f
        return Prediction(mean, std, lower, upper, n, n >= self.min_evidence)
