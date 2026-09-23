"""Strong-inference pre-registration: two rivals, named exclusions,
refusals booked against ground-truth labels.
"""
from __future__ import annotations

import pytest

from moth_honest.planted import EXERCISES_BY_ID
from moth_honest.prereg import (
    Hypothesis,
    Preregistration,
    PreregVerdict,
    grade_prereg,
    seal_prereg,
    verify_prereg,
)


def _h(bug_class: str = "buffer_overflow", excludes_on: str = "exercise-clean"):
    return Hypothesis(bug_class=bug_class, excludes_on=excludes_on)


def _p(ex_id: str, *hyps: Hypothesis, predict_refusal: bool = False,
       hunter: str = "hunter-x") -> Preregistration:
    return Preregistration(exercise_id=ex_id, hunter_id=hunter,
                           hypotheses=tuple(hyps), predict_refusal=predict_refusal)


def test_exactly_two_rival_hypotheses_required():
    with pytest.raises(ValueError, match="exactly 2"):
        _p("c-clean-001", _h())
    with pytest.raises(ValueError, match="exactly 2"):
        _p("c-clean-001", _h(), _h(), _h())


def test_hypothesis_must_name_its_exclusion():
    with pytest.raises(ValueError, match="excludes"):
        Hypothesis(bug_class="buffer_overflow", excludes_on="")


def test_correct_restraint_on_clean_exercise():
    ex = EXERCISES_BY_ID["c-clean-001"]
    v = grade_prereg(_p(ex.exercise_id, _h(), _h("double_free"),
                        predict_refusal=True),
                     ex, claimed=False, refused=True)
    assert v.refusal_label == "correct-restraint"
    assert not v.against_commitment


def test_missed_bug_when_restraint_meets_planted_bug():
    ex = EXERCISES_BY_ID["c-overflow-001"]
    v = grade_prereg(_p(ex.exercise_id, _h("double_free"),
                        _h("use_after_free"), predict_refusal=True),
                     ex, claimed=False, refused=True)
    assert v.refusal_label == "missed-bug"
    assert v.excluded == ("double_free", "use_after_free")
    assert v.surviving == ()


def test_abstention_without_prior_commitment():
    ex = EXERCISES_BY_ID["rust-clean-001"]
    v = grade_prereg(_p(ex.exercise_id, _h(), _h("unsafe_write")),
                     ex, claimed=False, refused=True)
    assert v.refusal_label == "abstention"
    assert v.against_commitment


def test_silence_is_abstention_not_restraint():
    ex = EXERCISES_BY_ID["js-clean-001"]
    v = grade_prereg(_p(ex.exercise_id, _h(), _h("eval_injection"),
                        predict_refusal=True),
                     ex, claimed=False, refused=False)
    assert v.refusal_label == "abstention"
    assert v.against_commitment


def test_claimed_round_is_not_a_refusal_event():
    ex = EXERCISES_BY_ID["js-eval-001"]
    v = grade_prereg(_p(ex.exercise_id, _h("eval_injection"), _h("xss")),
                     ex, claimed=True, refused=False)
    assert v.refusal_label == "claimed"
    assert v.surviving == ("eval_injection",)
    assert v.excluded == ("xss",)
    # surviving is corroborated, never confirmed — strong inference
    assert "confirmed" not in repr(v)


def test_seal_verify_round_trip_and_corpus_binding():
    preregs = (
        _p("c-clean-001", _h(), _h("double_free"), predict_refusal=True),
        _p("c-overflow-001", _h(), _h("double_free")),
    )
    grades = {
        "c-clean-001": grade_prereg(
            preregs[0], EXERCISES_BY_ID["c-clean-001"],
            claimed=False, refused=True),
    }
    rows = seal_prereg(preregs, grades=grades)
    ok, errors = verify_prereg([dict(r) for r in rows])
    assert ok, errors
    assert rows[0]["kind"] == "PREREG/v1"
    verdict_row = next(r for r in rows
                         if r.get("kind") == "PREREG-ROW/v1"
                         and r["exercise_id"] == "c-clean-001")
    assert verdict_row["verdict"]["refusal_label"] == "correct-restraint"


def test_tamper_detected():
    rows = seal_prereg((_p("c-clean-001", _h(), _h("double_free")),))
    broken = [dict(r) for r in rows]
    broken[1]["predict_refusal"] = True  # after sealing
    ok, errors = verify_prereg(broken)
    assert not ok
    assert any("row_hash" in e or "chain_hash" in e for e in errors)


def test_unknown_exercise_flagged_not_fatal():
    rows = seal_prereg((_p("no-such-exercise", _h(), _h()),))
    assert rows[1].get("note") == "unknown exercise"
    ok, errors = verify_prereg([dict(r) for r in rows])
    assert ok, errors
