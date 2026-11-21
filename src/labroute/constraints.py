"""Laboratory constraints checking.

This module answers Can this lab physically run this route ? 
It does not estimate chemical success likelihood; that is learned from outcomes

(see ``estimator.py``). Keeping the two separate is a core design principle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from .chem import canonicalize_smiles
from .models import Conditions, Route


@dataclass
class Inventory:
    """Available stock, in mmol, keyed by (canonical) SMILES."""

    stock_mmol: dict = field(default_factory=dict)

    def __post_init__(self):
        self.stock_mmol = {canonicalize_smiles(k): float(v) for k, v in self.stock_mmol.items()}

    def available(self, smiles: str) -> float:
        return self.stock_mmol.get(canonicalize_smiles(smiles), 0.0)

    def in_stock(self, smiles: str) -> bool:
        return self.available(smiles) > 0.0

    @classmethod
    def from_json(cls, path) -> "Inventory":
        with open(path, encoding="utf-8") as f:
            return cls(stock_mmol=json.load(f)["stock_mmol"])


@dataclass
class Equipment:
    """One instrument and what it can do in the lab."""

    name: str
    min_temp_c: float = -80.0
    max_temp_c: float = 250.0
    features: frozenset = frozenset()  # e.g. {"temperature", "microwave"}

    @classmethod
    def from_dict(cls, d: dict) -> "Equipment":
        return cls(
            name=d["name"],
            min_temp_c=d.get("min_temp_c", -80.0),
            max_temp_c=d.get("max_temp_c", 250.0),
            features=frozenset(d.get("features", [])),
        )

    def supports(self, cond: Conditions) -> bool:
        if cond.temperature_c is not None and not (
            self.min_temp_c <= cond.temperature_c <= self.max_temp_c
        ):
            return False
        return cond.required_features <= self.features


@dataclass
class LabProfile:
    inventory: Inventory
    equipment: list = field(default_factory=list)

    @classmethod
    def from_files(cls, inventory_path, equipment_path) -> "LabProfile":
        with open(equipment_path, encoding="utf-8") as f:
            eq = [Equipment.from_dict(d) for d in json.load(f)]
        return cls(Inventory.from_json(inventory_path), eq)


@dataclass(frozen=True)
class Issue:
    kind: str  # "reagent_shortfall" | "equipment_unavailable"
    detail: str
    step_index: Optional[int] = None


@dataclass
class FeasibilityReport:
    route_id: str
    issues: list = field(default_factory=list)
    leaves_in_stock_fraction: float = 1.0

    @property
    def operational_feasible(self) -> bool:
        return not self.issues


def assess_route(route: Route, lab: LabProfile, scale_mmol: float = 1.0) -> FeasibilityReport:
    """Check availability of starting materials and equipment capability for every step."""
    issues = []

    need = route.required_mmol(scale_mmol)
    leaves = route.leaves()
    in_stock = sum(1 for m in leaves if lab.inventory.in_stock(m))
    fraction = in_stock / len(leaves) if leaves else 1.0

    for smiles, amount in need.items():
        have = lab.inventory.available(smiles)
        if have < amount:
            issues.append(
                Issue(
                    "reagent_shortfall",
                    f"{smiles}: need {amount:g} mmol, have {have:g} mmol",
                )
            )

    for i, step in enumerate(route.steps):
        cond = step.conditions
        needs_equipment = cond.temperature_c is not None or bool(cond.required_features)
        if needs_equipment and not any(e.supports(cond) for e in lab.equipment):
            issues.append(
                Issue(
                    "equipment_unavailable",
                    f"step {i + 1} ({step.reaction_key}) needs "
                    f"temp={cond.temperature_c} features={sorted(cond.required_features)}",
                    step_index=i,
                )
            )

    return FeasibilityReport(route.route_id, issues, fraction)
