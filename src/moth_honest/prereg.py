"""Strong-inference pre-registration for hunter rounds.

A hunter that pre-registers commits, BEFORE seeing the exercise outcome,
to exactly two rival hypotheses and names the observation that would
exclude each. Refusals are then booked against ground-truth labels:

    correct-restraint  restraint on a clean exercise (the gate earned it)
    missed-bug         restraint on an exercise with planted bugs
    abstention         restraint (or silence) without a prior commitment

The point is Platt's: one hypothesis per experiment can explain anything;
two rivals plus named exclusions make the round falsifiable before the
receipt exists. A refusal counts as restraint only when it was predicted
— otherwise it is abstention, and the receipt says which.
"""
from __future__ import annotations

from dataclasses import dataclass

from .planted import EXERCISES_BY_ID, Exercise
from .receipts import corpus_hash
from .vendor_canonical import canonical_dumps
from .vendor_hashes import fnv1a_64_hex

GENESIS = "0" * 16

REFUSAL_LABELS = ("correct-restraint", "missed-bug", "abstention", "claimed")


@dataclass(frozen=True)
class Hypothesis:
    bug_class: str
    excludes_on: str  # the observation that would exclude this hypothesis

    def __post_init__(self) -> None:
        if not self.bug_class:
            raise ValueError("hypothesis bug_class must be named")
        if not self.excludes_on:
            raise ValueError("hypothesis must name what excludes it "
                             "(a hypothesis without an exclusion "
                             "observation cannot be falsified)")


@dataclass(frozen=True)
class Preregistration:
    exercise_id: str
    hunter_id: str
    hypotheses: tuple[Hypothesis, ...]
    predict_refusal: bool = False

    def __post_init__(self) -> None:
        if len(self.hypotheses) != 2:
            raise ValueError(
                f"strong inference requires exactly 2 rival hypotheses, "
                f"got {len(self.hypotheses)} — one hypothesis per round "
                f"can explain anything, which is why it needs no receipt")


@dataclass(frozen=True)
class PreregVerdict:
    exercise_id: str
    refusal_label: str
    excluded: tuple[str, ...]      # hypotheses the ground truth excluded
    surviving: tuple[str, ...]     # hypotheses still standing (NOT confirmed)
    against_commitment: bool       # refused/silent despite committing to claim


def _is_refusal_event(predict_refusal: bool, claimed: bool,
                      refused: bool) -> tuple[bool, bool]:
    """(is_refusal_event, against_commitment)."""
    if claimed:
        return False, False
    if refused:
        return True, not predict_refusal
    return True, True  # silence: no claims, no booked refusal


def grade_prereg(prereg: Preregistration, exercise: Exercise, *,
                 claimed: bool, refused: bool) -> PreregVerdict:
    truth_classes = {t.bug_class for t in exercise.ground_truth}
    excluded = tuple(h.bug_class for h in prereg.hypotheses
                     if h.bug_class not in truth_classes)
    surviving = tuple(h.bug_class for h in prereg.hypotheses
                      if h.bug_class in truth_classes)
    is_refusal, against = _is_refusal_event(prereg.predict_refusal,
                                            claimed, refused)
    if not is_refusal:
        label = "claimed"
    elif against:
        label = "abstention"
    elif exercise.ground_truth:
        label = "missed-bug"
    else:
        label = "correct-restraint"
    return PreregVerdict(exercise_id=prereg.exercise_id, refusal_label=label,
                         excluded=excluded, surviving=surviving,
                         against_commitment=against)


def seal_prereg(preregs: tuple[Preregistration, ...], *,
                grades: dict[str, PreregVerdict] | None = None
                ) -> list[dict]:
    """Hash-chained PREREG/v1 rows; header binds the live corpus."""
    header = {
        "kind": "PREREG/v1",
        "schema_version": "1.0",
        "producer": {"tool": "moth-honest", "module": "prereg"},
        "count": len(preregs),
        "corpus_hash": corpus_hash(),
    }
    rows: list[dict] = [header]
    for p in sorted(preregs, key=lambda x: x.exercise_id):
        row = {
            "kind": "PREREG-ROW/v1",
            "exercise_id": p.exercise_id,
            "hunter_id": p.hunter_id,
            "predict_refusal": p.predict_refusal,
            "hypotheses": [
                {"bug_class": h.bug_class, "excludes_on": h.excludes_on}
                for h in p.hypotheses
            ],
        }
        g = (grades or {}).get(p.exercise_id)
        if g is not None:
            row["verdict"] = {
                "refusal_label": g.refusal_label,
                "excluded": list(g.excluded),
                "surviving": list(g.surviving),
            }
        if p.exercise_id not in EXERCISES_BY_ID:
            row["note"] = "unknown exercise"
        rows.append(row)
    return _chain(rows)


def _row_digest(row: dict) -> str:
    return fnv1a_64_hex(canonical_dumps(row))


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


def verify_prereg(rows: list[dict]) -> tuple[bool, list[str]]:
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
    if not errors and rows and rows[0].get("kind") == "PREREG/v1":
        if rows[0].get("corpus_hash") != corpus_hash():
            errors.append("corpus_hash does not match installed corpus "
                          "(exercises changed after this prereg was sealed)")
    return (not errors), errors
