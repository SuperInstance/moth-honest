"""moth-honest CLI: plant exercises, evaluate reports, verify receipts."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .evaluate import HuntReport, evaluate
from .planted import EXERCISES, EXERCISES_BY_ID, materialize
from .receipts import seal, verify_rows
from .vendor_canonical import canonical_dumps
from .vendor_hashes import assert_pins


def _load_report(path: str) -> HuntReport:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    from .evaluate import Claim, Refusal
    return HuntReport(
        hunter_id=data["hunter_id"],
        claims=tuple(Claim(**c) for c in data.get("claims", [])),
        refusals=tuple(Refusal(**r) for r in data.get("refusals", [])),
    )


def cmd_plant(args: argparse.Namespace) -> int:
    selected = [e for e in EXERCISES if args.lang in (None, e.lang)]
    for e in selected:
        materialize(e, args.output)
        print(f"planted {e.exercise_id} ({len(e.ground_truth)} bug(s))")
    print(f"-> {args.output}/")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    assert_pins()
    report = _load_report(args.report)
    start = time.monotonic()
    result = evaluate(report, EXERCISES_BY_ID)
    wall_ms = int((time.monotonic() - start) * 1000)
    result.cost["wall_ms"] = wall_ms
    rows = seal(report, result)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(canonical_dumps(row).decode("utf-8") + "\n")
    t = {
        "tp": result.true_positives, "fp": result.false_positives,
        "fn": result.false_negatives,
        "refusals": result.correct_refusals,
        "precision": result.precision_q16 / 65536,
        "recall": result.recall_q16 / 65536,
        "f1": result.f1_q16 / 65536,
    }
    print(f"hunter={report.hunter_id} TP={t['tp']} FP={t['fp']} FN={t['fn']} "
          f"refusals={t['refusals']} P={t['precision']:.4f} R={t['recall']:.4f} "
          f"F1={t['f1']:.4f} -> {args.output}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    rows = [json.loads(l) for l in Path(args.corpus_eval).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok, errors = verify_rows(rows)
    if ok:
        print(f"OK: {args.corpus_eval} — receipt intact, corpus bound")
        return 0
    for e in errors:
        print(f"BROKEN: {e}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="moth-honest",
        description="The evaluator: planted-bug ground truth + honest-cost scoring",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plant = sub.add_parser("plant", help="materialize exercises to disk")
    p_plant.add_argument("--lang", default=None)
    p_plant.add_argument("-o", "--output", required=True)
    p_plant.set_defaults(func=cmd_plant)

    p_eval = sub.add_parser("evaluate", help="score a hunter report")
    p_eval.add_argument("--report", required=True)
    p_eval.add_argument("-o", "--output", required=True)
    p_eval.set_defaults(func=cmd_evaluate)

    p_ver = sub.add_parser("verify", help="verify a sealed evaluation receipt")
    p_ver.add_argument("corpus_eval")
    p_ver.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
