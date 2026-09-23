"""cells-bench: pinned-metric regression + panel E + adversarial gate."""
import json
from pathlib import Path

import pytest

from moth_honest.bench import (adversarial_review, build_panel,
                               splitmix64, verify_walk_rows,
                               walk_rows_to_report)
from moth_honest.evaluate import Claim, HuntReport, evaluate

WALKS = Path(__file__).resolve().parent.parent / "examples" / "bench" / "walks"

PINNED = {
    "w_auth-4e3c0068":    dict(tp=1, fp=0, fn=1, P=65536, R=32768, F1=43690),
    "w_bounds-4e3efc68":  dict(tp=1, fp=0, fn=1, P=65536, R=32768, F1=43690),
    "w_bounds-4e42fc68":  dict(tp=1, fp=0, fn=1, P=65536, R=32768, F1=43690),
    "w_echo_fp-79a9cd68": dict(tp=0, fp=0, fn=2, P=65536, R=0, F1=0),
    "w_roam-79a2c968":    dict(tp=0, fp=0, fn=2, P=65536, R=0, F1=0),
    "w_roam-79adc968":    dict(tp=0, fp=0, fn=2, P=65536, R=0, F1=0),
}


def _load(name):
    rows = [json.loads(l) for l in (WALKS / f"{name}.jsonl")
            .read_text().splitlines() if l.strip()]
    return rows


@pytest.mark.parametrize("name", sorted(PINNED))
def test_fixture_receipts_verify(name):
    ok, errors = verify_walk_rows(_load(name))
    assert ok, errors


@pytest.mark.parametrize("name", sorted(PINNED))
def test_pinned_metrics_rederived(name):
    """Regression control: evaluator output over the committed battery
    must match the pinned constants exactly, re-derived every run."""
    rows = _load(name)
    genome_hash = next(r["genome_hash"] for r in rows
                       if r.get("kind") == "HUNT/v1")
    report = walk_rows_to_report(rows, genome_hash)
    res = evaluate(report, build_panel(include_vulns=True))
    pin = PINNED[name]
    assert res.true_positives == pin["tp"]
    assert res.false_positives == pin["fp"]
    assert res.false_negatives == pin["fn"]
    assert res.precision_q16 == pin["P"]
    assert res.recall_q16 == pin["R"]
    assert res.f1_q16 == pin["F1"]


def test_panel_e_healthy_cells_absorb_claims():
    """Panel E (all-healthy): claims on vuln geography become unknown-
    exercise hallucinations (fp); declared healthy cells stay clean."""
    rows = _load("w_bounds-4e3efc68")
    report = walk_rows_to_report(rows, "test")
    res = evaluate(report, build_panel(include_vulns=False))
    assert res.false_positives >= 1  # parse claim vs panel E = hallucinated
    for ex_id, per in res.per_exercise.items():
        if per.get("note") != "unknown exercise":
            assert per["fn"] == 0  # healthy truth stays clean


def test_undeclared_geography_books_refusal_not_claim():
    rows = [{
        "kind": "FINDING/v1", "file": "mystery.c", "fn": "mystery",
        "taint_path": ["mystery.c:mystery"], "evidence": "ab12",
        "genome_hash": "g" * 16, "dice_seed": 1, "tick": 0,
    }]
    report = walk_rows_to_report(rows, "test")
    assert report.claims == ()
    assert len(report.refusals) == 1
    assert report.refusals[0].note == "undeclared_geography"


def test_splitmix64_pinned_vectors():
    assert splitmix64(0xA0A, 0) == 0x133F09730A842375
    assert splitmix64(0xA0A, 2) == 0x16FF835C1C528FAB
    assert splitmix64(1, 0) == 0x910A2DEC89025CC1
    assert splitmix64(0xC0CA9E, 7) == 0xC0AEF6656C9CB06E


def test_adversarial_gate_overturns_tolerance_luck():
    """Claim at parse.c:10 (dial 7, distance 3): CONFIRMED under the
    primary tolerance of 3, REFUTED under judge-seed 0xA0B's re-drawn
    tolerance of 2 — the verdict was tolerance-luck and gets overturned,
    booked, never deleted. (Judge tols at 0xA0B: parse=2, route=3.)"""
    panel = build_panel(include_vulns=True)
    report = HuntReport(
        hunter_id="edge", claims=(Claim(
            exercise_id="parse", file="parse.c", line=10,
            bug_class="bounds_check_bypass", confidence_q16=32768),))
    primary = evaluate(report, panel)
    assert primary.per_exercise["parse"]["outcome"] == "CONFIRMED"
    verdict = adversarial_review(report, panel, judge_seed=0xA0B)
    assert verdict.confirmed == []
    assert len(verdict.overturned) == 1
    ov = verdict.overturned[0]
    assert ov["exercise"] == "parse"
    assert ov["judge_tolerance"] == 2
    assert ov["judge_outcome"] != "CONFIRMED"
    rows = verdict.seal()
    assert rows[0]["row_hash"] and rows[0]["chain_hash"]
    assert all(r["kind"] == "ADVERSARIAL_REFUSAL/v1" for r in rows)


def test_adversarial_gate_confirms_honest_findings():
    panel = build_panel(include_vulns=True)
    report = HuntReport(
        hunter_id="honest", claims=(Claim(
            exercise_id="parse", file="parse.c", line=7,
            bug_class="bounds_check_bypass", confidence_q16=32768),))
    verdict = adversarial_review(report, panel)
    assert verdict.confirmed == ["parse"]
    assert verdict.overturned == []
