import json
import math

import pytest

from labroute import (
    BetaSuccessEstimator,
    Conditions,
    Equipment,
    Inventory,
    LabProfile,
    Outcome,
    OutcomeStore,
    Route,
    Step,
    SuccessCriterion,
    rank_routes,
    rank_by_stock,
    assess_route,
)
from labroute.adapters import routes_from_tree_dicts
from labroute.evaluate import brier_score, expected_calibration_error, top_k_success_ratio


def simple_route(rid="r1", key="acyl", cond=Conditions()):
    return Route(rid, [Step(key, "P", ("A", "B"), cond)])


def lab(stock, equipment=None):
    return LabProfile(Inventory(stock), equipment or [])


# constraints

def test_feasible_when_stock_sufficient():
    report = assess_route(simple_route(), lab({"A": 5, "B": 5}), scale_mmol=2.0)
    assert report.operational_feasible
    assert report.leaves_in_stock_fraction == 1.0


def test_reagent_shortfall_reported():
    report = assess_route(simple_route(), lab({"A": 5, "B": 1}), scale_mmol=2.0)
    assert not report.operational_feasible
    assert any(i.kind == "reagent_shortfall" and "B" in i.detail for i in report.issues)


def test_equipment_temperature_and_features():
    cond = Conditions(temperature_c=-20, required_features=frozenset({"inert_atmosphere"}))
    route = simple_route(cond=cond)
    stock = {"A": 5, "B": 5}
    ok = Equipment("cryo", -78, 25, frozenset({"inert_atmosphere"}))
    too_warm = Equipment("hotplate", 20, 200, frozenset({"inert_atmosphere"}))
    no_feature = Equipment("cryo2", -78, 25, frozenset())
    assert assess_route(route, lab(stock, [ok])).operational_feasible
    assert not assess_route(route, lab(stock, [too_warm])).operational_feasible
    assert not assess_route(route, lab(stock, [no_feature])).operational_feasible


def test_intermediates_not_required_from_stock():
    route = Route(
        "two_step",
        [Step("a", "P", ("I", "B")), Step("b", "I", ("A",))],
    )
    assert set(route.leaves()) == {"B", "A"}
    report = assess_route(route, lab({"A": 2, "B": 2}))
    assert report.operational_feasible


# outcomes

def test_outcome_store_roundtrip(tmp_path):
    store = OutcomeStore(tmp_path / "o.jsonl")
    crit = SuccessCriterion(60)
    store.append(Outcome.from_yield("k", 75, crit))
    store.append(Outcome.from_yield("k", 20, crit))
    loaded = store.load()
    assert [o.success for o in loaded] == [True, False]
    assert loaded[0].yield_pct == 75


def test_estimator_uses_failures_and_flags_unknown():
    est = BetaSuccessEstimator().fit(
        [Outcome("k", True)] * 4 + [Outcome("k", False)] * 1
    )
    known = est.predict("k")
    unknown = est.predict("never_seen")
    assert known.sufficient_evidence and 0.5 < known.mean < 0.9
    assert not unknown.sufficient_evidence
    assert unknown.mean == pytest.approx(0.5)
    assert unknown.std > known.std


def test_local_outcomes_outweigh_public():
    public = [Outcome("k", True, source="public")] * 10
    local = [Outcome("k", False, source="lab")] * 10
    only_public = BetaSuccessEstimator().fit(public).predict("k").mean
    adapted = BetaSuccessEstimator().fit(public + local).predict("k").mean
    assert only_public > 0.7
    assert adapted < 0.3


# ranking

def test_infeasible_routes_rank_last_even_if_likely_to_succeed():
    est = BetaSuccessEstimator().fit(
        [Outcome("good", True)] * 10 + [Outcome("meh", True)] * 3 + [Outcome("meh", False)] * 3
    )
    routes = [
        Route("blocked", [Step("good", "P", ("X",))]),
        Route("ok", [Step("meh", "P", ("A",))]),
    ]
    ranked = rank_routes(routes, lab({"A": 5}), est)
    assert [r.route_id for r in ranked] == ["ok", "blocked"]
    assert ranked[1].operational_feasible is False
    assert all(r.assumes_independence for r in ranked)


def test_limited_evidence_is_flagged():
    est = BetaSuccessEstimator()
    ranked = rank_routes([simple_route()], lab({"A": 5, "B": 5}), est)
    assert ranked[0].all_steps_have_evidence is False
    assert ranked[0].notes


def test_baseline_ignores_reliability():
    routes = [
        Route("short", [Step("k", "P", ("A", "Z"))]),
        Route("full", [Step("k", "P", ("A", "B"))]),
    ]
    order = rank_by_stock(routes, Inventory({"A": 1, "B": 1}))
    assert order[0][0] == "full"


# adapters

def test_aizynth_tree_conversion():
    tree = {
        "type": "mol", "smiles": "T", "children": [
            {"type": "reaction", "metadata": {"classification": "c1"}, "children": [
                {"type": "mol", "smiles": "M", "children": [
                    {"type": "reaction", "metadata": {"template_hash": "h2"}, "children": [
                        {"type": "mol", "smiles": "S1"}]}]},
                {"type": "mol", "smiles": "S2"}]}]}
    (route,) = routes_from_tree_dicts([tree])
    assert [s.reaction_key for s in route.steps] == ["c1", "h2"]
    assert set(route.leaves()) == {"S1", "S2"}


# evaluation

def test_calibration_metrics():
    probs, outs = [0.9, 0.9, 0.1, 0.1], [True, True, False, False]
    assert brier_score(probs, outs) == pytest.approx(0.01)
    assert expected_calibration_error(probs, outs) == pytest.approx(0.1)


def test_top_k_success_ratio():
    assert top_k_success_ratio(["a", "b"], {"a": True, "b": False}, k=2) == 0.5
    assert math.isnan(top_k_success_ratio(["x"], {}, k=1))


# cli

def test_cli_rank_and_log(tmp_path, capsys):
    from labroute.cli import main

    store = tmp_path / "out.jsonl"
    assert main(["log", "--store", str(store), "--reaction-key", "k", "--yield", "80"]) == 0
    assert main(["log", "--store", str(store), "--reaction-key", "k", "--result", "failure"]) == 0
    assert len(OutcomeStore(store).load()) == 2
    code = main([
        "rank",
        "--routes", "examples/routes.json",
        "--inventory", "examples/inventory.json",
        "--equipment", "examples/equipment.json",
        "--outcomes", "examples/outcomes.jsonl",
        "--conditions", "examples/conditions.json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "route_3" in out and "Not feasible" in out
