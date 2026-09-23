"""Evaluate hunter reports against planted ground truth.

HuntReport: claims the hunter made. EvalResult: what was true, what was
fiction, what the honesty cost. Q16 arithmetic everywhere; refuse never
round. A correct refusal on a clean exercise counts toward precision
discipline, not as a miss.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .planted import Exercise, GroundTruthBug, from_q16, q16_floor, to_q16

DEFAULT_LINE_TOLERANCE = 3

VALID_OUTCOMES = ("CONFIRMED", "REFUTED", "REFUSAL")


@dataclass(frozen=True)
class Claim:
    exercise_id: str
    file: str
    line: int
    bug_class: str
    confidence_q16: int


@dataclass(frozen=True)
class Refusal:
    exercise_id: str
    note: str = ""


@dataclass(frozen=True)
class HuntReport:
    hunter_id: str
    claims: tuple[Claim, ...]
    refusals: tuple[Refusal, ...] = ()

    @property
    def exercised_ids(self) -> set[str]:
        return {c.exercise_id for c in self.claims} | {r.exercise_id for r in self.refusals}


@dataclass
class EvalResult:
    hunter_id: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    correct_refusals: int = 0
    per_exercise: dict = field(default_factory=dict)
    cost: dict = field(default_factory=dict)

    @property
    def precision_q16(self) -> int:
        """Vacuous convention: no claims made -> no false claims -> 1.0.

        But note the rumor-mill limit: a HuntReport with zero claims AND
        zero refusals is indistinguishable from one that refused
        everything. That is why refusals must be booked explicitly —
        the receipt is the difference between a gate and a vibe.
        """
        denom = self.true_positives + self.false_positives
        if denom == 0:
            return to_q16(1.0)
        return q16_floor(self.true_positives / denom)

    @property
    def recall_q16(self) -> int:
        denom = self.true_positives + self.false_negatives
        if denom == 0:
            return to_q16(1.0)
        return q16_floor(self.true_positives / denom)

    @property
    def f1_q16(self) -> int:
        p, r = from_q16(self.precision_q16), from_q16(self.recall_q16)
        if p + r == 0:
            return 0
        return q16_floor(2 * p * r / (p + r))


def _match(claim: Claim, truth: GroundTruthBug, tolerance: int) -> bool:
    return (claim.file == truth.file
            and abs(claim.line - truth.line) <= tolerance
            and claim.bug_class == truth.bug_class)


def evaluate(report: HuntReport, exercises: dict[str, Exercise],
             *, line_tolerance: int = DEFAULT_LINE_TOLERANCE,
             wall_ms: int = 0) -> EvalResult:
    result = EvalResult(hunter_id=report.hunter_id)
    claimed: dict[str, list[Claim]] = {}
    for c in report.claims:
        claimed.setdefault(c.exercise_id, []).append(c)
    refused_ids = {r.exercise_id for r in report.refusals}

    for ex_id, exercise in exercises.items():
        truth = list(exercise.ground_truth)
        claims = claimed.pop(ex_id, [])
        explicit_refusal = ex_id in refused_ids
        matched: set[int] = set()
        fp = 0
        for claim in claims:
            hit = next((i for i, t in enumerate(truth)
                        if i not in matched and _match(claim, t, line_tolerance)),
                       None)
            if hit is None:
                fp += 1
            else:
                matched.add(hit)
        fn = len(truth) - len(matched)
        refused_cleanly = (not truth and not claims and explicit_refusal)
        result.per_exercise[ex_id] = {
            "outcome": ("CONFIRMED" if matched and not fp and not fn else
                        "REFUSAL" if refused_cleanly else "REFUTED"),
            "tp": len(matched), "fp": fp, "fn": fn,
        }
        result.true_positives += len(matched)
        result.false_positives += fp
        result.false_negatives += fn
        result.correct_refusals += int(refused_cleanly)

    # Claims/refusals for unknown exercises: hallucinated terrain.
    for ex_id, claims in claimed.items():
        result.false_positives += len(claims)
        result.per_exercise[ex_id] = {
            "outcome": "REFUTED", "tp": 0, "fp": len(claims), "fn": 0,
            "note": "unknown exercise",
        }

    result.cost = {
        "claims_spent": len(report.claims),
        "exercises_run": len(exercises),
        "wall_ms": wall_ms,
    }
    return result
