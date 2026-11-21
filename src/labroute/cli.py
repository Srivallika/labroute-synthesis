"""CLI commands for route ranking and outcome logging in labroute.

  labroute rank --routes routes.json --inventory inventory.json --equipment equipment.json \
                --outcomes outcomes.jsonl [--conditions conditions.json] [--scale 1.0]
  labroute check-data --outcomes outcomes.jsonl
  labroute log  --store outcomes.jsonl --reaction-key KEY (--yield 72 | --result failure) [--min-yield 50]
"""

from __future__ import annotations

import argparse
import json
import sys

from .adapters.aizynthfinder import routes_from_tree_dicts
from .constraints import LabProfile
from .estimator import BetaSuccessEstimator
from .models import Conditions, Outcome, OutcomeStore, SuccessCriterion
from .quality import quality_report
from .ranking import rank_routes, rank_by_stock


def _load_conditions(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        return {k: Conditions.from_dict(v) for k, v in json.load(f).items()}


def cmd_rank(args) -> int:
    with open(args.routes, encoding="utf-8") as f:
        tree_dicts = json.load(f)
    routes = routes_from_tree_dicts(tree_dicts, _load_conditions(args.conditions))
    lab = LabProfile.from_files(args.inventory, args.equipment)
    estimator = BetaSuccessEstimator().fit(OutcomeStore(args.outcomes).load())

    print("Baseline ranking (starting materials in stock):")
    for rid, score in rank_by_stock(routes, lab.inventory):
        print(f"  {rid}: {score:.2f} of starting materials in stock")

    print("\nRanking considering constraints and reliability:")
    for r in rank_routes(routes, lab, estimator, args.scale, args.risk_aversion):
        status = "feasible" if r.operational_feasible else "Not feasible"
        ev = "" if r.all_steps_have_evidence else "  [limited evidence]"
        print(
            f"  #{r.rank} {r.route_id}: {status}, "
            f"est. success={r.success_mean:.2f}, conservative={r.conservative_score:.2f}{ev}"
        )
        for issue in r.report.issues:
            print(f"      - {issue.kind}: {issue.detail}")
        for note in r.notes:
            print(f"      - note: {note}")
    print("\nNote: route level success assumes independent steps; validate before relying on it.")
    return 0


def cmd_log(args) -> int:
    criterion = SuccessCriterion(args.min_yield)
    if args.yield_pct is not None:
        outcome = Outcome.from_yield(
            args.reaction_key, args.yield_pct, criterion, source=args.source, notes=args.notes
        )
    else:
        outcome = Outcome(
            args.reaction_key,
            success=(args.result == "success"),
            source=args.source,
            notes=args.notes,
        )
    OutcomeStore(args.store).append(outcome)
    print(f"Logged: {outcome.reaction_key} success={outcome.success}")
    return 0


def cmd_check(args) -> int:
    report = quality_report(OutcomeStore(args.outcomes).load())
    print(f"Records: {report['total']}  trusted: {report['trusted']}  excluded: {report['excluded']}")
    for source, counts in report["yield_status_by_source"].items():
        print(f"  {source}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("Public records without a valid yield are excluded as success labels.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="labroute")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("rank", help="assess operational feasibility and rank routes for a laboratory")
    r.add_argument("--routes", required=True, help="JSON list of AiZynthFinder route dicts")
    r.add_argument("--inventory", required=True)
    r.add_argument("--equipment", required=True)
    r.add_argument("--outcomes", required=True, help="JSONL outcome store")
    r.add_argument("--conditions", help="JSON: reaction_key -> conditions")
    r.add_argument("--scale", type=float, default=1.0, help="mmol per step")
    r.add_argument("--risk-aversion", type=float, default=1.0)
    r.set_defaults(func=cmd_rank)

    lg = sub.add_parser("log", help="append an experimental outcome")
    lg.add_argument("--store", required=True)
    lg.add_argument("--reaction-key", required=True)
    g = lg.add_mutually_exclusive_group(required=True)
    g.add_argument("--yield", dest="yield_pct", type=float)
    g.add_argument("--result", choices=["success", "failure"], help="use when no yield is known")
    lg.add_argument("--min-yield", type=float, default=50.0)
    lg.add_argument("--source", default="lab", choices=["lab", "public"])
    lg.add_argument("--notes", default="")
    lg.set_defaults(func=cmd_log)
    ck = sub.add_parser("check-data", help="report label-quality problems in an outcome store")
    ck.add_argument("--outcomes", required=True)
    ck.set_defaults(func=cmd_check)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
