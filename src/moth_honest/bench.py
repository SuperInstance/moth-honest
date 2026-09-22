"""cells-bench: healthy-cell regression controls + adversarial-review gate.

B's plan, experiment 1 companion: synthetic target batteries with known
truth labels; hunter receipts scored by the evaluator; pinned metrics
re-derived every run. The panel E doctrine: a healthy cell must be
classifiable as healthy — the evaluator's job is to agree with planted
truth, not with the hunter.

Adversarial-review gate: the judge-the-judge mechanic INSIDE the
evaluator. The campaign verdict is re-examined under an independent dice
stream with a re-drawn line tolerance; any exercise whose outcome FLIPS
under re-examination is overturned — booked ADVERSARIAL_REFUSAL/v1,
never deleted.

Receipts, not dependencies: the bench consumes SEALED walk receipts
(committed fixtures under examples/bench/). moth-cells is a dev-time
fixture generator only (dev/gen_bench_fixtures.py); CI never installs it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .evaluate import (Claim, EvalResult, HuntReport, Refusal, evaluate)
from .planted import Exercise, GroundTruthBug
from .receipts import _chain
from .vendor_canonical import canonical_dumps
from .vendor_hashes import fnv1a_64_hex

GENESIS = "0" * 16


def verify_walk_rows(rows: list[dict]) -> tuple[bool, list[str]]:
    """Re-derive a sealed walk receipt (moth-cells chain law, vendored —
    the bench consumes receipts without importing the kernel)."""
    errors: list[str] = []
    prev = GENESIS
    for idx, row in enumerate(rows):
        r = dict(row)
        try:
            rh, ch = r.pop("row_hash"), r.pop("chain_hash")
        except KeyError as exc:
            errors.append(f"row {idx}: missing {exc}")
            break
        if rh != fnv1a_64_hex(canonical_dumps(r)):
            errors.append(f"row {idx}: row_hash mismatch")
        if ch != fnv1a_64_hex(bytes.fromhex(prev) + bytes.fromhex(rh)):
            errors.append(f"row {idx}: chain_hash mismatch")
        prev = ch
    return (not errors), errors


# vendored dice, family recipe (splitmix64) — provenance: moth-cells
# model.py; reimplemented here so the evaluator stays stdlib-only and the
# adversarial stream is INDEPENDENT of the hunter's stream.
MASK64 = (1 << 64) - 1


def splitmix64(seed: int, tick: int) -> int:
    z = (seed + 0x9E3779B97F4A7C15 + tick * 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


# ---------------------------------------------------------------- panels
# Claim vocabulary: kernel findings name (file, fn, cell); the evaluator
# matches bug_class. The adapter declares the translation — a bench whose
# labels smuggle in hunter language would grade itself. Healthy cells get
# declared classes too: claims on them honestly count as false positives
# against their empty ground truth (the panel-E gate).

CLAIM_CLASS = {
    "parse": "bounds_check_bypass",
    "route": "unauthenticated_route",
    "echo": "format_string_risk",
    "math": "integer_overflow_risk",
    "idle": "dead_code_risk",
}

# Declared panel geography: where each cell's line lives in its file.
# The kernel books findings by (file, fn, cell_id); the evaluator scores
# by (file, line, bug_class). This table is the bench's honest translator
# — a claim whose cell isn't here is refused as undeclared geography,
# never silently mapped.
PANEL_LINE = {
    "parse.c:parse": 7, "route.c:route": 3, "echo.c:echo": 2,
    "math.c:math": 2, "idle.c:idle": 2,
}

PANEL_CODE = {
    "parse": "#include <string.h>\nvoid parse(char *in) {\n"
             "    char buf[8];\n    strcpy(buf, in); /* BUG */\n}\n",
    "route": "int route(int fd) {\n    return dispatch(fd); /* BUG */\n}\n",
    "echo": "void echo(const char *m) { printf(\"%s\", m); }\n",
    "math": "int add(int a, int b) { return a + b; }\n",
    "idle": "void idle(void) { }\n",
}


def build_panel(include_vulns: bool = True) -> dict[str, Exercise]:
    """Five cells: two planted-vuln (parse/route) + three healthy
    (echo/math/idle). Panel E = include_vulns=False (all healthy).
    Exercise ids ARE the cell fn names — identifier drift between the
    kernel's vocabulary and the evaluator's is a false-positive machine."""
    gt = {
        "parse": (GroundTruthBug(file="parse.c", line=7,
                                 bug_class="bounds_check_bypass"),),
        "route": (GroundTruthBug(file="route.c", line=3,
                                 bug_class="unauthenticated_route"),),
    }
    ids = ("parse", "route", "echo", "math", "idle") if include_vulns \
        else ("echo", "math", "idle")
    return {
        ex_id: Exercise(
            exercise_id=ex_id, lang="c",
            code={f"{ex_id}.c": PANEL_CODE[ex_id]},
            ground_truth=gt.get(ex_id, ()),
            difficulty_hint=1 << 15, notes="cells-bench panel cell")
        for ex_id in ids
    }


def panel_terrain_rows(include_vulns: bool = True) -> list[dict]:
    """Corpus-terrain rows (moth-corpus canonical) for fixture walks."""
    taint = {"parse": 3, "route": 3, "echo": 1, "math": 0, "idle": 0}
    names = ("parse", "route", "echo", "math", "idle") if include_vulns \
        else ("echo", "math", "idle")
    return [{
        "file_path": f"{name}.c", "language": "c", "loc": 12,
        "surface": {"name": name, "entry_points": 65536 // 2,
                    "taint_marks": (65536 * taint[name]) // 4},
    } for name in names]


# ------------------------------------------------- walk receipt adapter

def walk_rows_to_report(rows: list[dict], genome_hash: str) -> HuntReport:
    """Sealed walk receipt (moth-cells HUNT/FINDING/REFUSAL rows) → the
    evaluator's HuntReport. exercise_id = the walked fn; bug_class is
    translated via the DECLARED CLAIM_CLASS vocabulary; lines come from
    the DECLARED PANEL_LINE geography. Confidences derive from the sealed
    evidence hash (first 16 bits) — never invented, never float."""
    claims: list[Claim] = []
    refusals: list[Refusal] = []
    for r in rows:
        if r.get("kind") == "FINDING/v1":
            ex_id = r["fn"]
            cls = CLAIM_CLASS.get(ex_id)
            cell_id = r["taint_path"][0]
            line = PANEL_LINE.get(cell_id)
            if cls is None or line is None:
                # claim on geography the bench didn't declare: the honest
                # move is a refusal — the evaluator counts unknown claims
                # as hallucinated terrain, and so do we.
                refusals.append(Refusal(exercise_id=ex_id,
                                        note="undeclared_geography"))
                continue
            conf = int(str(r["evidence"])[:4], 16)
            claims.append(Claim(exercise_id=ex_id, file=r["file"],
                                line=line, bug_class=cls,
                                confidence_q16=conf))
        elif r.get("kind") == "REFUSAL/v1" and r.get("cell_id"):
            refusals.append(Refusal(exercise_id=r["cell_id"].split(":")[-1],
                                    note=r.get("reason", "")))
    return HuntReport(hunter_id=genome_hash,
                      claims=tuple(claims), refusals=tuple(refusals))


# ----------------------------------------------- adversarial-review gate

@dataclass
class AdversarialVerdict:
    confirmed: list[str] = field(default_factory=list)   # exercise ids
    overturned: list[dict] = field(default_factory=list)  # ADVERSARIAL_REFUSAL rows

    def seal(self) -> list[dict]:
        """Chain-seal the verdict: accepted findings as ADVERSARIAL/v1
        confirmed rows, overturns as ADVERSARIAL_REFUSAL/v1."""
        rows = [{"kind": "ADVERSARIAL/v1", "event": "confirmed",
                 "exercise": ex} for ex in self.confirmed]
        rows.extend(self.overturned)
        return _chain(rows)


def adversarial_review(report: HuntReport, exercises: dict[str, Exercise],
                       judge_seed: int = 0xA0A) -> AdversarialVerdict:
    """Re-derive the campaign under an INDEPENDENT dice stream: the
    judge re-runs evaluate() with a dice-drawn line tolerance (1..3)
    per exercise. Outcome flips are overturned — booked, never deleted.
    The judge uses the same ground truth; only the tolerance is re-drawn,
    so an overturn means the primary verdict was tolerance-luck."""
    primary = evaluate(report, exercises)
    verdict = AdversarialVerdict()
    for idx, ex_id in enumerate(sorted(exercises)):
        tol = 1 + splitmix64(judge_seed, idx) % 3
        re = evaluate(report, {ex_id: exercises[ex_id]}, line_tolerance=tol)
        p_out = primary.per_exercise.get(ex_id, {}).get("outcome")
        r_out = re.per_exercise.get(ex_id, {}).get("outcome")
        if p_out == "CONFIRMED" and r_out != "CONFIRMED":
            verdict.overturned.append({
                "kind": "ADVERSARIAL_REFUSAL/v1", "exercise": ex_id,
                "reason": "verdict_not_rerenderivable",
                "primary_outcome": p_out, "judge_outcome": r_out,
                "judge_tolerance": tol,
                "detail": re.per_exercise.get(ex_id, {}),
            })
        elif p_out == "CONFIRMED":
            verdict.confirmed.append(ex_id)
    return verdict
