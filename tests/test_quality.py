import random

from labroute import BetaSuccessEstimator, Outcome
from labroute.cli import main
from labroute.evaluate import label_randomization_control
from labroute.models import OutcomeStore
from labroute.quality import quality_report, trusted_outcomes, yield_status


def test_yield_status():
    assert yield_status(None) == "missing"
    assert yield_status(-3) == "negative"
    assert yield_status(104) == "over_100"
    assert yield_status(0) == "ok" and yield_status(100) == "ok"


def test_public_needs_valid_yield_lab_may_omit():
    outs = [
        Outcome("a", True, 80, source="public"),
        Outcome("a", True, None, source="public"),
        Outcome("a", True, 140, source="public"),
        Outcome("a", False, None, source="lab"),
        Outcome("a", True, -5, source="lab"),
    ]
    kept = trusted_outcomes(outs)
    assert len(kept) == 2
    assert {(o.source, o.yield_pct) for o in kept} == {("public", 80), ("lab", None)}
    rep = quality_report(outs)
    assert rep["excluded"] == 3 and rep["total"] == 5


def _signal_data(n=200):
    rng = random.Random(1)
    out = []
    for _ in range(n):
        key = rng.choice(["good", "bad"])
        ok = rng.random() < (0.9 if key == "good" else 0.1)
        out.append(Outcome(key, ok, source="lab"))
    return out


def test_randomization_control_detects_signal():
    data = _signal_data()
    res = label_randomization_control(data[:100], data[100:], BetaSuccessEstimator, n_repeats=30)
    assert res["real_brier"] < res["shuffled_brier_mean"]
    assert res["p_value"] < 0.1


def test_randomization_control_no_signal():
    rng = random.Random(2)
    data = [Outcome(rng.choice("abcd"), rng.random() < 0.5) for _ in range(200)]
    res = label_randomization_control(data[:100], data[100:], BetaSuccessEstimator, n_repeats=30)
    assert res["p_value"] > 0.05


def test_check_data_cli(tmp_path, capsys):
    path = tmp_path / "o.jsonl"
    store = OutcomeStore(path)
    store.append(Outcome("a", True, 150, source="public"))
    store.append(Outcome("a", True, 70, source="public"))
    assert main(["check-data", "--outcomes", str(path)]) == 0
    assert "excluded: 1" in capsys.readouterr().out
