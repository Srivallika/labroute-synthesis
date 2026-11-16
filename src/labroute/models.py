"""Core data models: routes, steps, conditions, and experimental outcomes.

Design note: operational constraints (reagents, equipment) are modeled separately
from chemical success likelihood, which is learned from recorded outcomes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .chem import canonical


@dataclass(frozen=True)
class Conditions:
    """Operating requirements of one reaction step."""

    temperature_c: Optional[float] = None
    required_features: frozenset = frozenset()  # e.g. {"inert_atmosphere", "microwave"}

    @classmethod
    def from_dict(cls, d: dict) -> "Conditions":
        return cls(
            temperature_c=d.get("temperature_c"),
            required_features=frozenset(d.get("required_features", [])),
        )


@dataclass(frozen=True)
class Step:
    """One reaction step. ``reaction_key`` groups reactions of the same type/class."""

    reaction_key: str
    product: str
    reactants: tuple
    conditions: Conditions = Conditions()
    equivalents: Optional[tuple] = None  # per reactant; defaults to 1.0 each


@dataclass
class Route:
    """An ordered list of steps leading to a target molecule."""

    route_id: str
    steps: list

    def products(self) -> set:
        return {canonicalize_smiles(s.product) for s in self.steps}

    def leaves(self) -> list:
        """Starting materials: reactants not produced by any step in the route."""
        produced = self.products()
        seen, out = set(), []
        for step in self.steps:
            for r in step.reactants:
                c = canonicalize_smiles(r)
                if c not in produced and c not in seen:
                    seen.add(c)
                    out.append(c)
        return out

    def required_mmol(self, scale_mmol: float = 1.0) -> dict:
        """Amount of each starting material needed.

        Simplification (prototype): every step runs at ``scale_mmol`` of each
        reactant times its equivalents. Yields and stoichiometric propagation
        through intermediates are not modeled yet.
        """
        produced = self.products()
        need: dict = {}
        for step in self.steps:
            eqs = step.equivalents or (1.0,) * len(step.reactants)
            for r, eq in zip(step.reactants, eqs):
                c = canonicalize_smiles(r)
                if c in produced:
                    continue
                need[c] = need.get(c, 0.0) + scale_mmol * eq
        return need


@dataclass(frozen=True)
class SuccessCriterion:
    """Explicit definition of experimental success, e.g. isolated yield above a threshold."""

    min_yield_pct: float = 50.0

    def is_success(self, yield_pct: float) -> bool:
        return yield_pct >= self.min_yield_pct


@dataclass
class Outcome:
    """One recorded experiment. Failures must be recorded, not only successes."""

    reaction_key: str
    success: bool
    yield_pct: Optional[float] = None
    source: str = "lab"  # "lab" (local, authorized) or "public" (public dataset)
    conditions: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    @classmethod
    def from_yield(
        cls, reaction_key: str, yield_pct: float, criterion: SuccessCriterion, **kwargs
    ) -> "Outcome":
        return cls(
            reaction_key=reaction_key,
            success=criterion.is_success(yield_pct),
            yield_pct=yield_pct,
            **kwargs,
        )


class OutcomeStore:
    """Append-only JSON Lines store of outcomes (portable, diff-friendly, no dependencies)."""

    def __init__(self, path):
        self.path = Path(path)

    def append(self, outcome: Outcome) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(outcome)) + "\n")

    def load(self) -> list:
        if not self.path.exists():
            return []
        out = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(Outcome(**json.loads(line)))
        return out

    def extend(self, outcomes: Iterable[Outcome]) -> None:
        for o in outcomes:
            self.append(o)
