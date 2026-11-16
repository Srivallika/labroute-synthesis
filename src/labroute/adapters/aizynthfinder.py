"""Adapter: AiZynthFinder chemical synthesis routes -> labroute Route objects.

AiZynthFinder serializes each route as a nested dict:
    {"type": "mol", "smiles": ..., "in_stock": ..., "children": [
        {"type": "reaction", "smiles": ..., "metadata": {...}, "children": [<mol nodes>]}]}

This adapter converts those dicts so routes can be assessed against a laboratory's
constraints and re-ranked. Labroute checks inventory, equipment requirements and available experimental evidence
Route ranking prioritizes routes using your assessment logic.

AiZynthFinder does not predict reaction conditions, so conditions are supplied through an
optional ``conditions_lookup`` mapping reaction_key -> Conditions.
"""

from __future__ import annotations

from typing import Optional

from ..models import Conditions, Route, Step

_KEY_FIELDS = ("classification", "template_hash", "template")


def extract_reaction_key(metadata: dict) -> str:
    """Group reactions into classes. Prefers a reaction classification, then template id."""
    for field in _KEY_FIELDS:
        value = (metadata or {}).get(field)
        if value:
            return str(value)
    return "unclassified"


def _walk(mol_node: dict, steps: list, conditions_lookup: dict) -> None:
    for child in mol_node.get("children", []):
        if child.get("type") != "reaction":
            continue
        reactant_nodes = [c for c in child.get("children", []) if c.get("type") == "mol"]
        key = extract_reaction_key(child.get("metadata", {}))
        steps.append(
            Step(
                reaction_key=key,
                product=mol_node["smiles"],
                reactants=tuple(c["smiles"] for c in reactant_nodes),
                conditions=conditions_lookup.get(key, Conditions()),
            )
        )
        for c in reactant_nodes:
            _walk(c, steps, conditions_lookup)


def routes_from_tree_dicts(
    tree_dicts: list,
    conditions_lookup: Optional[dict] = None,
    id_prefix: str = "route",
) -> list:
    routes = []
    for i, tree in enumerate(tree_dicts, start=1):
        steps: list = []
        _walk(tree, steps, conditions_lookup or {})
        routes.append(Route(route_id=f"{id_prefix}_{i}", steps=steps))
    return routes


def routes_from_finder(finder, conditions_lookup: Optional[dict] = None) -> list:
    """Convert routes from a finished ``aizynthfinder.aizynthfinder.AiZynthFinder`` run.

    Call ``finder.tree_search()`` and ``finder.build_routes()`` first.
    """
    return routes_from_tree_dicts(finder.routes.dicts, conditions_lookup)
