"""A deliberately mediocre regex hunter — the demo of honest scoring.

Claims 3 bugs: 1 true (c-overflow), 1 false positive (rust-clean, where
nothing is wrong), 1 wrong-class (js-eval claimed as the right line but
wrong class — actually let us make it a near-miss line instead).
Refuses 1 clean exercise explicitly; stays silent on everything else.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from moth_honest import Claim, HuntReport, Refusal, evaluate, seal, verify_rows
from moth_honest.planted import EXERCISES_BY_ID
from moth_honest.vendor_canonical import canonical_dumps


def main() -> int:
    report = HuntReport(
        hunter_id="mock-regex-hunter-0.1",
        claims=(
            Claim("c-overflow-001", "main.c", 8, "buffer_overflow", 65536 // 2),
            Claim("rust-clean-001", "main.rs", 3, "unsafe_write", 65536 // 4),
            Claim("js-eval-001", "run.js", 6, "eval_injection", 65536 // 2),
        ),
        refusals=(
            Refusal("c-clean-001", "snprintf bounded copy seen"),
        ),
    )
    result = evaluate(report, EXERCISES_BY_ID, wall_ms=0)
    result.cost["wall_ms"] = 12
    rows = seal(report, result)

    out = Path(__file__).parent / "mock_hunter.eval.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(canonical_dumps(row).decode("utf-8") + "\n")
    ok, errors = verify_rows([dict(r) for r in rows])
    print(f"receipt {'intact' if ok else errors} -> {out}")
    print(f"mock hunter honest score: "
          f"P={result.precision_q16 / 65536:.4f} "
          f"R={result.recall_q16 / 65536:.4f} "
          f"F1={result.f1_q16 / 65536:.4f} "
          f"(TP={result.true_positives} FP={result.false_positives} "
          f"FN={result.false_negatives} refusals={result.correct_refusals})")
    print("MOTH claims 78.2% on real targets. This mock claims nothing —")
    print("it demonstrates what an honest, receipted, mediocre hunt looks like.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
