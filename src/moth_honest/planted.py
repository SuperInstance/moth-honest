"""Planted-bug ground truth: exercises with known answers.

The duke-lab lesson institutionalized: apparent skill rankings may be
cheap-descent optimism. Every hunter that wants trust must re-derive its
number here first. Some exercises are CLEAN — a hunter that claims bugs
on clean code books false positives; one that refuses books honesty.
"""
from __future__ import annotations

from dataclasses import dataclass

# Q16: fixed-point with denominator 65536; refuse never round.
Q16_DENOM = 65536


def to_q16(value: float) -> int:
    """Refuse-never-round: integers only, error if not exact.

    For CONSTRUCTORS (difficulty hints, pins). Metrics that divide use
    q16_floor instead — deterministically truncate toward zero and say so.
    """
    scaled = value * Q16_DENOM
    if scaled != int(scaled):
        raise ValueError(f"not exactly representable in Q16: {value}")
    return int(scaled)


def q16_floor(value: float) -> int:
    """Deterministic truncation toward zero, never rounded up.

    Division makes most ratios inexact in Q16 (2/5 of 65536 is
    26214.4). The JEV floor refuses to round UP — truncation is the
    documented, reproducible choice, identical on every substrate.
    """
    return int(value * Q16_DENOM)


def from_q16(value: int) -> float:
    return value / Q16_DENOM


@dataclass(frozen=True)
class GroundTruthBug:
    file: str
    line: int
    bug_class: str


@dataclass(frozen=True)
class Exercise:
    exercise_id: str
    lang: str
    code: dict[str, str]  # path -> content
    ground_truth: tuple[GroundTruthBug, ...]
    difficulty_hint: int  # Q16, 0..1
    notes: str = ""


C_OVERFLOW = r'''#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void greet(char *name) {
    char buf[16];
    strcpy(buf, name);          /* BUG: unbounded copy, line 7 */
    printf("hello %s\n", buf);
}

int main(int argc, char **argv) {
    if (argc > 1) greet(argv[1]);
    return 0;
}
'''

C_CLEAN = r'''#include <stdio.h>
#include <string.h>

void greet(const char *name) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%s", name);
    printf("hello %s\n", buf);
}

int main(int argc, char **argv) {
    if (argc > 1) greet(argv[1]);
    return 0;
}
'''

C_DOUBLE_FREE = r'''#include <stdlib.h>

int process(int n) {
    int *p = malloc(sizeof(int) * n);
    if (!p) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) total += p[i];
    free(p);
    free(p);                    /* BUG: double free, line 9 */
    return total;
}
'''

RUST_UNSAFE = '''use std::env;

fn main() {
    let arg = env::args().nth(1).unwrap();
    let p = arg.as_ptr() as *mut u8;
    unsafe {
        std::ptr::write(p, 0);  // BUG: write through borrowed ptr, line 7
    }
    println!("{}", arg);
}
'''

RUST_CLEAN = '''use std::env;

fn main() {
    let arg = env::args().nth(1).unwrap_or_default();
    println!("{}", arg);
}
'''

JS_EVAL = '''const user = process.argv[2] || "world";
const code = "console.log('hello ' + " + JSON.stringify(user) + ")";
eval(code);                     // BUG: eval on derived input, line 3
'''

JS_CLEAN = '''const user = process.argv[2] || "world";
console.log("hello " + user);
'''

EXERCISES: tuple[Exercise, ...] = (
    Exercise("c-overflow-001", "c",
             {"main.c": C_OVERFLOW},
             (GroundTruthBug("main.c", 7, "buffer_overflow"),),
             to_q16(0.25), "unbounded strcpy into stack buffer"),
    Exercise("c-clean-001", "c",
             {"main.c": C_CLEAN},
             (), to_q16(0.25), "clean: snprintf bounded; any claim here is a FP"),
    Exercise("c-double-free-001", "c",
             {"proc.c": C_DOUBLE_FREE},
             (GroundTruthBug("proc.c", 9, "double_free"),),
             to_q16(0.5), "second free of same pointer"),
    Exercise("rust-unsafe-write-001", "rust",
             {"main.rs": RUST_UNSAFE},
             (GroundTruthBug("main.rs", 7, "unsafe_write"),),
             to_q16(0.5), "write through pointer cast from &str"),
    Exercise("rust-clean-001", "rust",
             {"main.rs": RUST_CLEAN},
             (), to_q16(0.25), "clean: unwrap_or_default; any claim here is a FP"),
    Exercise("js-eval-001", "js",
             {"run.js": JS_EVAL},
             (GroundTruthBug("run.js", 3, "eval_injection"),),
             to_q16(0.25), "eval on input-derived string"),
    Exercise("js-clean-001", "js",
             {"run.js": JS_CLEAN},
             (), to_q16(0.25), "clean: plain concat; any claim here is a FP"),
)

EXERCISES_BY_ID = {e.exercise_id: e for e in EXERCISES}


def materialize(exercise: Exercise, out_dir) -> None:
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for rel, content in exercise.code.items():
        target = out / exercise.exercise_id / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
