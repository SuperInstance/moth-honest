"""Receipted evaluation runs — sealed like everything else in the family.

EVAL/v1 header (corpus hash binds the exact exercises) + VERDICT/v1 rows
per exercise. verify re-derives from residue: the caught-lie law.
"""
from __future__ import annotations

from .evaluate import EvalResult, HuntReport
from .planted import EXERCISES
from .vendor_canonical import canonical_dumps
from .vendor_hashes import fnv1a_64_hex

GENESIS = "0" * 16


def corpus_hash() -> str:
    """Hash of the full planted corpus — binds exercise content."""
    payload = [
        {
            "exercise_id": e.exercise_id,
            "code": e.code,
            "ground_truth": [
                {"file": t.file, "line": t.line, "bug_class": t.bug_class}
                for t in e.ground_truth
            ],
        }
        for e in EXERCISES
    ]
    return fnv1a_64_hex(canonical_dumps(payload))


def _row_digest(row: dict) -> str:
    return fnv1a_64_hex(canonical_dumps(row))


def seal(report: HuntReport, result: EvalResult) -> list[dict]:
    header = {
        "kind": "EVAL/v1",
        "schema_version": "1.0",
        "producer": {"tool": "moth-honest", "version": "0.1.0"},
        "hunter_id": report.hunter_id,
        "corpus_hash": corpus_hash(),
        "cost": result.cost,
        "totals": {
            "tp": result.true_positives,
            "fp": result.false_positives,
            "fn": result.false_negatives,
            "correct_refusals": result.correct_refusals,
            "precision_q16": result.precision_q16,
            "recall_q16": result.recall_q16,
            "f1_q16": result.f1_q16,
        },
    }
    rows: list[dict] = [header]
    for ex_id in sorted(result.per_exercise):
        d = result.per_exercise[ex_id]
        rows.append({
            "kind": "VERDICT/v1",
            "exercise_id": ex_id,
            "outcome": d["outcome"],
            "tp": d["tp"], "fp": d["fp"], "fn": d["fn"],
            **({"note": d["note"]} if "note" in d else {}),
        })
    return _chain(rows)


def _chain(rows: list[dict]) -> list[dict]:
    out, prev = [], GENESIS
    for row in rows:
        r = dict(row)
        rh = _row_digest(r)
        ch = fnv1a_64_hex(bytes.fromhex(prev) + bytes.fromhex(rh))
        r["row_hash"] = rh
        r["chain_hash"] = ch
        out.append(r)
        prev = ch
    return out


def verify_rows(rows: list[dict]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    prev = GENESIS
    for idx, row in enumerate(rows):
        try:
            rh, ch = row.pop("row_hash"), row.pop("chain_hash")
        except KeyError as exc:
            errors.append(f"row {idx}: missing {exc}")
            break
        expected_rh = _row_digest(row)
        if rh != expected_rh:
            errors.append(f"row {idx}: row_hash mismatch")
        expected_ch = fnv1a_64_hex(bytes.fromhex(prev) + bytes.fromhex(expected_rh))
        if ch != expected_ch:
            errors.append(f"row {idx}: chain_hash mismatch")
        prev = ch
    # corpus binding: header's corpus_hash must match live corpus
    if not errors and rows and rows[0].get("kind") == "EVAL/v1":
        if rows[0].get("corpus_hash") != corpus_hash():
            errors.append("corpus_hash does not match installed corpus "
                          "(exercises changed after this eval was sealed)")
    return (not errors), errors
