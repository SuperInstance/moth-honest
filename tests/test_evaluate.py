"""Evaluation semantics: TP/FP/FN, refusals, Q16 metrics."""
from moth_honest import Claim, HuntReport, Refusal, evaluate
from moth_honest.planted import EXERCISES_BY_ID, to_q16


def _report(claims=(), refusals=(), hunter="test-hunter"):
    return HuntReport(hunter_id=hunter, claims=tuple(claims),
                      refusals=tuple(refusals))


def test_perfect_hunter():
    report = _report(claims=[
        Claim("c-overflow-001", "main.c", 8, "buffer_overflow", 0),
        Claim("c-double-free-001", "proc.c", 10, "double_free", 0),
        Claim("rust-unsafe-write-001", "main.rs", 8, "unsafe_write", 0),
        Claim("js-eval-001", "run.js", 4, "eval_injection", 0),
    ])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.true_positives == 4
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.precision_q16 == to_q16(1.0)
    assert result.recall_q16 == to_q16(1.0)
    assert result.f1_q16 == to_q16(1.0)


def test_line_tolerance():
    report = _report(claims=[Claim("c-overflow-001", "main.c", 10, "buffer_overflow", 0)])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.true_positives == 1  # truth at line 8, tol 3


def test_outside_tolerance_is_fp():
    report = _report(claims=[Claim("c-overflow-001", "main.c", 20, "buffer_overflow", 0)])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.true_positives == 0
    assert result.false_positives == 1


def test_wrong_class_is_fp_and_fn():
    report = _report(claims=[Claim("c-overflow-001", "main.c", 8, "double_free", 0)])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.false_positives == 1
    # globally every real bug is still missed (4 FN); per-exercise the
    # claim is 1 FP and leaves that exercise's truth unmatched
    assert result.false_negatives == 4
    assert result.per_exercise["c-overflow-001"]["fp"] == 1
    assert result.per_exercise["c-overflow-001"]["fn"] == 1


def test_claim_on_clean_is_fp():
    report = _report(claims=[Claim("rust-clean-001", "main.rs", 3, "unsafe_write", 0)])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.false_positives == 1
    assert result.correct_refusals == 0


def test_explicit_refusal_on_clean_counts():
    report = _report(refusals=[Refusal("c-clean-001")])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.correct_refusals == 1
    assert result.per_exercise["c-clean-001"]["outcome"] == "REFUSAL"


def test_silence_on_clean_is_not_a_refusal():
    report = _report()
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.correct_refusals == 0
    assert result.per_exercise["c-clean-001"]["outcome"] == "REFUTED" or \
           result.per_exercise["c-clean-001"]["outcome"] != "REFUSAL"


def test_missed_bug_is_fn():
    report = _report()
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.false_negatives == 4
    assert result.recall_q16 == 0


def test_unknown_exercise_is_hallucination():
    report = _report(claims=[Claim("nope-999", "x.c", 1, "buffer_overflow", 0)])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.false_positives == 1
    assert result.per_exercise["nope-999"]["outcome"] == "REFUTED"


def test_partial_match_counts_fn():
    report = _report(claims=[Claim("c-overflow-001", "main.c", 8, "buffer_overflow", 0)])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.true_positives == 1
    assert result.false_negatives == 3  # the other three buggy exercises


def test_vacuous_precision_convention():
    report = _report()
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.precision_q16 == to_q16(1.0)  # no false claims made


def test_q16_exactness_of_ratios():
    report = _report(claims=[
        Claim("c-overflow-001", "main.c", 8, "buffer_overflow", 0),
        Claim("rust-clean-001", "main.rs", 3, "unsafe_write", 0),
    ])
    result = evaluate(report, EXERCISES_BY_ID)
    assert result.precision_q16 == to_q16(1 / 2)      # exact
    assert result.recall_q16 == to_q16(1 / 4)         # exact
    # F1 = 2TP/(2TP+FP+FN) = 2/5; Q16 cannot hold it -> floor, never round
    from moth_honest.planted import q16_floor
    assert result.f1_q16 == q16_floor(2 * (1 / 2) * (1 / 4) / ((1 / 2) + (1 / 4)))


def test_cost_fields():
    report = _report(claims=[Claim("c-overflow-001", "main.c", 8, "buffer_overflow", 0)])
    result = evaluate(report, EXERCISES_BY_ID, wall_ms=42)
    assert result.cost["claims_spent"] == 1
    assert result.cost["exercises_run"] == len(EXERCISES_BY_ID)
    assert result.cost["wall_ms"] == 42


def test_custom_tolerance():
    report = _report(claims=[Claim("c-overflow-001", "main.c", 12, "buffer_overflow", 0)])
    near = evaluate(report, EXERCISES_BY_ID, line_tolerance=5)
    far = evaluate(report, EXERCISES_BY_ID, line_tolerance=3)
    assert near.true_positives == 1
    assert far.true_positives == 0
