"""Dev-only fixture generator for the cells-bench (NOT run in CI).

Requires moth-cells in the dev venv:
    pip install git+https://github.com/SuperInstance/moth-cells@moth-cells-k1
    python dev/gen_bench_fixtures.py

Generates sealed hunter-walk receipts over the panel terrain and writes
them under examples/bench/walks/. The bench consumes these receipts
(receipts, not dependencies); CI only re-derives and scores them.
Each walk seals its own chain — chains never merge.

When you regenerate: the pinned metric constants in tests/test_bench.py
MUST be re-derived from the fresh receipts and updated in the same
commit — pinned numbers are never trusted, they are re-verified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from moth_honest.bench import (build_panel, panel_terrain_rows,
                               verify_walk_rows, walk_rows_to_report)
from moth_honest.evaluate import evaluate

OUT = Path(__file__).resolve().parent.parent / "examples" / "bench" / "walks"

BATTERY = [
    # name, probe cell idx, genome seeds
    ("w_bounds", 0, [0xB1, 0xB2]),
    ("w_auth", 1, [0xB3]),
    ("w_echo_fp", 2, [0xB4]),      # healthy cell: claims here would be FPs
    ("w_roam", None, [0xB5, 0xB6]),
]


def main() -> int:
    from moth_cells import Genome, from_corpus_rows, walk  # dev-only import
    cells = from_corpus_rows(panel_terrain_rows(include_vulns=True))
    OUT.mkdir(parents=True, exist_ok=True)
    panel = build_panel(include_vulns=True)
    pin = {}
    for name, probe_at, seeds in BATTERY:
        for s in seeds:
            g = Genome(seed=s, move_weights=(49152, 16384, 0, 0, 0),
                       attention_bias=8192)
            _, rows = walk(g, cells, 30, probe_at=probe_at)
            ok, errs = verify_walk_rows(rows)
            assert ok, errs
            path = OUT / f"{name}-{g.genome_id[:8]}.jsonl"
            with path.open("w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")
            report = walk_rows_to_report(rows, g.genome_id)
            res = evaluate(report, panel)
            pin[f"{name}-{g.genome_id[:8]}"] = {
                "tp": res.true_positives, "fp": res.false_positives,
                "fn": res.false_negatives,
                "P": res.precision_q16, "R": res.recall_q16, "F1": res.f1_q16,
            }
            print(f"{name}-{g.genome_id[:8]}: sealed {len(rows)} rows")
    print("\nPIN THESE CONSTANTS in tests/test_bench.py:")
    print(json.dumps(pin, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
