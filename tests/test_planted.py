"""Planted corpus and ground-truth integrity."""
import pytest

from moth_honest.planted import (EXERCISES, EXERCISES_BY_ID, GroundTruthBug,
                                 materialize, to_q16)
from moth_honest.vendor_hashes import assert_pins, fnv1a_64_hex


def test_pins():
    assert_pins()


def test_seven_exercises():
    assert len(EXERCISES) == 7


def test_exercise_ids_unique():
    ids = [e.exercise_id for e in EXERCISES]
    assert len(ids) == len(set(ids))


def test_buggy_exercises_have_ground_truth():
    buggy = [e for e in EXERCISES if "clean" not in e.exercise_id]
    assert len(buggy) == 4
    assert all(len(e.ground_truth) >= 1 for e in buggy)


def test_clean_exercises_empty_truth():
    clean = [e for e in EXERCISES if "clean" in e.exercise_id]
    assert len(clean) == 3
    assert all(e.ground_truth == () for e in clean)


def test_ground_truth_lines_point_at_real_code(tmp_path):
    for e in EXERCISES:
        materialize(e, tmp_path)
        for bug in e.ground_truth:
            lines = (tmp_path / e.exercise_id / bug.file).read_text().splitlines()
            assert 1 <= bug.line <= len(lines)


def test_ground_truth_line_marks_bug(tmp_path):
    """The cited line must actually look like the bug class."""
    for e in EXERCISES:
        materialize(e, tmp_path)
        for bug in e.ground_truth:
            line = (tmp_path / e.exercise_id / bug.file).read_text().splitlines()[bug.line - 1]
            assert "BUG" in line, f"{e.exercise_id}:{bug.line} does not cite a BUG"


def test_materialize_all(tmp_path):
    for e in EXERCISES:
        materialize(e, tmp_path)
    assert len(list(tmp_path.iterdir())) == len(EXERCISES)


def test_q16_refuses_nonexact():
    with pytest.raises(ValueError):
        to_q16(1 / 3)


def test_q16_exact():
    assert to_q16(0.25) == 16384
