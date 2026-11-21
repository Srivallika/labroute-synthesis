# labroute

An open-source Python prototype for **assessing the operational feasibility of AI-generated chemical
synthesis routes and learning from laboratory outcomes**. It sits on top of retrosynthesis planners such as
[AiZynthFinder](https://github.com/MolecularAI/aizynthfinder) and does three things:

1. **Assesses operational feasibility** of each proposed route against a laboratory's real inventory and equipment
   (`constraints.py`), kept separate from chemical success likelihood. It does not predict or guarantee chemical
   success or safety.
2. **Logs experimental outcomes, including failures**, in a simple open format (`models.py`,
   JSON Lines) so laboratories can build their own training data.
3. **Ranks routes** using operational feasibility plus laboratory-adaptive success estimates with
   explicit uncertainty (`estimator.py`, `ranking.py`), compared against a stock-only baseline.

> **Status: early research prototype.** Nothing here has been validated against real experimental
> outcomes. The example data in `examples/` is invented for demonstration only.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

labroute rank \
  --routes examples/routes.json --inventory examples/inventory.json \
  --equipment examples/equipment.json --outcomes examples/outcomes.jsonl \
  --conditions examples/conditions.json

labroute log --store my_outcomes.jsonl --reaction-key amine_acylation_anhydride --yield 82
labroute log --store my_outcomes.jsonl --reaction-key nitro_reduction --result failure
```

### Use with AiZynthFinder

```python
from aizynthfinder.aizynthfinder import AiZynthFinder
from labroute import BetaSuccessEstimator, OutcomeStore, rank_routes
from labroute.adapters import routes_from_finder
from labroute.constraints import LabProfile

finder = AiZynthFinder(configfile="config.yml")
finder.stock.select("zinc")
finder.expansion_policy.select("uspto")
finder.target_smiles = "CC(=O)Nc1ccc(O)cc1"
finder.tree_search()
finder.build_routes()

routes = routes_from_finder(finder)
lab = LabProfile.from_files("inventory.json", "equipment.json")
estimator = BetaSuccessEstimator().fit(OutcomeStore("outcomes.jsonl").load())
for r in rank_routes(routes, lab, estimator):
    print(r.rank, r.route_id, r.operational_feasible, round(r.conservative_score, 2))
```

AiZynthFinder's tree format and metadata keys can differ between versions. Check
`adapters/aizynthfinder.py` against the version you install.

## Design principles

- **Operational feasibility is separate from chemical success.** A route can be likely to work
  chemically but impossible in a given lab, or the reverse.
- **Honest scope.** Software checks of inventory and equipment cannot guarantee that a route is safe or
  will work chemically. Evidence is kept in three tiers: simulated constraints, historical experimental
  data, and prospective laboratory validation.
- **Failures are first-class data.** Every outcome records whether it met an explicit success
  criterion (`SuccessCriterion`, e.g. yield above a threshold).
- **Unknown means unknown.** Reaction classes with too little evidence are flagged, not guessed.
- **Laboratory adaptation.** Public-data outcomes are down-weighted so a lab's own outcomes
  dominate as they accumulate.

## Validate labels before using them

Yields mined from patents or other text sources can be missing, negative, over 100%, or a mix of
crude and isolated values. Do not treat them as success labels without checking.

```bash
labroute check-data --outcomes outcomes.jsonl
```

## Known limitations (read before drawing conclusions)

- Route-level success is the **product of step-level estimates, assuming independence**. This is a
  baseline; shared conditions and intermediates violate it. It is reported in every result
  (`assumes_independence`) and must be tested against observed route-level outcomes.
- Amounts are in **mmol** at a uniform scale per step; yields are not propagated through
  intermediates.
- Reactions are grouped by a **class key** (AiZynthFinder classification or template). Finer
  featurization and ML models belong in a later module behind the same `predict` interface.
- Retrospective benchmarks (see `evaluate.py`) can assess calibration and ranking, but they cannot
  show improved real-world synthesis success. That requires prospective laboratory validation.

See `ROADMAP.md` for planned releases.
