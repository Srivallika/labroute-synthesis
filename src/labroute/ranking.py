"""Route ranking: a stock-only baseline versus constraint- and reliability-aware ranking.

IMPORTANT: route-level success is computed here as a product of step-level estimates,
which assumes steps are independent. That assumption is known to be questionable
(shared conditions, intermediates, downstream processing). It is reported in every
result (``assumes_independence``) and must be tested against observed route-level
outcomes before any claim is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .constraints import FeasibilityReport, Inventory, LabProfile, assess_route
from .estimator import BetaSuccessEstimator
from .models import Route


@dataclass
class RankedRoute:
    route_id: str
    rank: int
    operational_feasible: bool
    success_mean: float
    conservative_score: float
    all_steps_have_evidence: bool
    n_steps: int
    report: FeasibilityReport
    assumes_independence: bool = True
    notes: list = field(default_factory=list)


def rank_by_stock(routes: list, inventory: Inventory) -> list:
    """Baseline similar in spirit to stock-aware scoring: fraction of starting
    materials in stock, then fewer steps. Returns [(route_id, score), ...]."""
    scored = []
    for r in routes:
        leaves = r.leaves()
        frac = sum(1 for m in leaves if inventory.in_stock(m)) / len(leaves) if leaves else 1.0
        scored.append((r.route_id, frac, len(r.steps)))
    scored.sort(key=lambda t: (-t[1], t[2]))
    return [(rid, frac) for rid, frac, _ in scored]


def rank_routes(
    routes: list,
    lab: LabProfile,
    estimator: BetaSuccessEstimator,
    scale_mmol: float = 1.0,
    risk_aversion: float = 1.0,
) -> list:
    """Rank routes: operationally feasible routes first, then by a conservative
    success score (mean minus ``risk_aversion`` x std per step, multiplied across steps),
    then fewer steps."""
    results = []
    for route in routes:
        report = assess_route(route, lab, scale_mmol)
        mean_prod, cons_prod, evidence_ok, notes = 1.0, 1.0, True, []
        for step in route.steps:
            p = estimator.predict(step.reaction_key)
            mean_prod *= p.mean
            cons_prod *= max(0.0, p.mean - risk_aversion * p.std)
            if not p.sufficient_evidence:
                evidence_ok = False
                notes.append(
                    f"insufficient evidence for '{step.reaction_key}' (n={p.n_effective:g})"
                )
        results.append(
            RankedRoute(
                route_id=route.route_id,
                rank=0,
                operational_feasible=report.operational_feasible,
                success_mean=mean_prod,
                conservative_score=cons_prod,
                all_steps_have_evidence=evidence_ok,
                n_steps=len(route.steps),
                report=report,
                notes=notes,
            )
        )
    results.sort(key=lambda r: (not r.operational_feasible, -r.conservative_score, r.n_steps))
    for i, r in enumerate(results, start=1):
        r.rank = i
    return results
