"""moth-honest — the evaluator.

Planted-bug ground truth + honest-cost scoring for receipted hunters.
The duke-lab sigma-wall doctrine institutionalized: no hunter's claimed
number (MOTH's self-reported 78.2% included) is trusted until it is
re-derived here, against ground truth, at honest cost.

Vacuous-precision convention + explicit refusals: a HuntReport with zero
claims AND zero refusals is indistinguishable from one that refused
everything — the receipt is the difference between a gate and a vibe.
"""

from .evaluate import (Claim, EvalResult, HuntReport, Refusal, evaluate)
from .planted import EXERCISES, EXERCISES_BY_ID, Exercise, GroundTruthBug
from .receipts import corpus_hash, seal, verify_rows
from .vendor_hashes import PINNED_VECTORS, assert_pins, fnv1a_64, fnv1a_64_hex

__version__ = "0.1.0"

__all__ = [
    "EXERCISES",
    "EXERCISES_BY_ID",
    "Claim",
    "EvalResult",
    "Exercise",
    "GroundTruthBug",
    "HuntReport",
    "PINNED_VECTORS",
    "Refusal",
    "__version__",
    "assert_pins",
    "corpus_hash",
    "evaluate",
    "fnv1a_64",
    "fnv1a_64_hex",
    "seal",
    "verify_rows",
]
