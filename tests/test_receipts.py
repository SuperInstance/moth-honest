"""Receipts: seal, verify, tamper-detect, corpus binding."""
import json

from moth_honest import Claim, HuntReport, Refusal, corpus_hash, evaluate, seal, verify_rows
from moth_honest.planted import EXERCISES_BY_ID
from moth_honest.vendor_canonical import canonical_dumps


def _sealed():
    report = HuntReport(
        hunter_id="receipt-test",
        claims=(Claim("c-overflow-001", "main.c", 8, "buffer_overflow", 0),),
        refusals=(Refusal("c-clean-001"),),
    )
    result = evaluate(report, EXERCISES_BY_ID, wall_ms=7)
    return seal(report, result)


def test_seal_verify_roundtrip():
    rows = _sealed()
    ok, errors = verify_rows([dict(r) for r in rows])
    assert ok, errors


def test_header_shape():
    rows = _sealed()
    h = rows[0]
    assert h["kind"] == "EVAL/v1"
    assert h["corpus_hash"] == corpus_hash()
    assert h["totals"]["tp"] == 1
    assert "precision_q16" in h["totals"]


def test_verdict_outcomes_valid():
    rows = _sealed()
    for r in rows[1:]:
        assert r["outcome"] in ("CONFIRMED", "REFUTED", "REFUSAL")


def test_determinism():
    assert _sealed() == _sealed()


def test_tamper_detected():
    rows = _sealed()
    forged = [dict(r) for r in rows]
    forged[1]["outcome"] = "CONFIRMED"  # flip a verdict
    ok, errors = verify_rows(forged)
    assert not ok
    assert any("row_hash" in e for e in errors)


def test_insert_detected():
    rows = _sealed()
    forged = [dict(r) for r in rows]
    extra = dict(forged[1])
    extra["exercise_id"] = "forged-001"
    extra.pop("row_hash"); extra.pop("chain_hash")
    forged.insert(2, extra)
    ok, errors = verify_rows(forged)
    assert not ok
    # popped-hash forgery trips the missing-field refusal; copied-hash
    # forgery trips row_hash; re-pointed tails trip chain_hash —
    # any refusal is correct, the chain does not judge which
    assert errors


def test_canonical_json_lines():
    rows = _sealed()
    for r in rows:
        line = canonical_dumps(r).decode("utf-8")
        assert json.loads(line) == r  # canonical form reparses to equal dict
