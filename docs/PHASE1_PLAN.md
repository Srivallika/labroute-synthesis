# Phase 1 plan: foundation, data, baselines

**Status: planned. Nothing in this plan has been built or run yet.** Target: v0.1 by the end of February 2027
(see `ROADMAP.md`). Dates are planning targets, not guarantees.

## Goal

A reproducible benchmark on public high-throughput experimentation (HTE) data that shows how well simple
baselines predict whether a reaction meets an explicit success criterion, with calibration diagnostics and a
shuffled-label control. This phase tests the evaluation pipeline. It does not test the final method.

## What this phase cannot show

- It cannot show improved real-world synthesis success. That needs prospective laboratory validation.
- HTE yields are assay-based measurements (for example, UV peak-area percent), not isolated yields, and each
  dataset covers only a few reaction classes. Results are benchmark results, not evidence of general laboratory
  performance.

## Steps

1. **Pick one dataset first.** Candidates named in the endeavor statement: HiTEA (King-Smith et al., 2024), the
   Buchwald-Hartwig and Suzuki-Miyaura sets in `rxn4chemistry/rxn_yields`, and the Tarricone et al. (2026) files
   in SURF format. Before using any of them, confirm (a) the license of the data itself, not only of the code
   repository, (b) how the yield was measured, and (c) that zero-yield and low-yield reactions are present. Use
   the full files, not "positive-only" subsets.
2. **Write a loader.** Convert each row to an `Outcome` with `source="public"`, `yield_pct`, and the plate or
   batch identifier stored in `conditions`. Define the success criterion explicitly (for example, yield at or
   above a threshold) and report results at more than one threshold. Run `labroute check-data` and report how
   many records were excluded and why.
3. **Split by plate or date, not at random.** Train on some plates and test on held-out plates. Report how the
   success rate varies between plates.
4. **Run baselines.** (a) The global success rate. (b) The per-reaction-class success rate. (c)
   `BetaSuccessEstimator`. Note that with a coarse class key (c) is close to (b), so the first real experiment is
   a finer key, such as ligand or base, chosen before looking at test results.
5. **Evaluate.** Brier score, reliability table and expected calibration error (`evaluate.py`), plus
   `label_randomization_control`. Credit a model only where it clearly beats the shuffled-label control.
6. **Write results.** A script, `scripts/run_phase1.py`, writes `results/phase1_<dataset>.json` and a short
   `results/PHASE1_REPORT.md` that records the dataset version, the date it was obtained, the commit hash, the
   random seeds, the numbers, and the limitations above.
7. **Release v0.1.** Tag the release, update the README status, and confirm that the continuous-integration
   run is passing.

## Done when

- One command reproduces the report from a clean clone.
- Tests pass in continuous integration.
- The report states its limitations and does not claim more than the data can show.
