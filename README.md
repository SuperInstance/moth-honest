# moth-honest

**The evaluator.** Planted-bug ground truth + honest-cost scoring for receipted hunters.

MOTH (the AI kernel-security hunting family) self-reports **78.2% on real targets**.
That number is a claim, not a fact. moth-honest is the fleet's answer: *our own
number before yours is trusted* — the duke-lab sigma-wall doctrine
("apparent skill may be cheap-descent optimism") applied to security hunting.

## What it does

1. **Plants bugs with known answers** — 7 exercises across C, Rust, and JS:
   buffer overflow, double-free, unsafe write, eval injection — plus 3 **clean**
   exercises where any claim is a false positive by construction.
2. **Scores hunter reports** — TP/FP/FN with a configurable line tolerance,
   per-exercise verdicts, and an explicit **refusal** track: a hunter that books
   "checked, nothing there" on clean code earns `correct_refusals`; silence earns nothing.
   A HuntReport with zero claims and zero refusals is indistinguishable from one
   that refused everything — the receipt is the difference between a gate and a vibe.
3. **Seals the evaluation as a chained receipt** — `EVAL/v1` header (corpus hash
   binds the exact exercises) + `VERDICT/v1` rows, FNV-1a-64 row/chain hashes over
   canonical JSON (byte-identical across substrates). `verify` re-derives from residue:
   tampered verdicts, inserted rows, and stale corpus hashes are all refused.

All measured fields are **Q16 fixed-point** (denominator 65536). Refuse never round:
exact values only for constructors; ratios truncate toward zero deterministically
and say so. No float ever crosses a substrate boundary as an identity.

## Honest cost

Every evaluation books its cost: `claims_spent`, `exercises_run`, `wall_ms`.
A hunter that spends 400 claims to find 4 bugs is scored against one that
spends 40. Accuracy without cost is how rumor mills dress up for dinner.

## Strong inference (pre-registration)

`moth_honest.prereg`: a hunter can pre-register a round BEFORE seeing
the outcome — exactly two rival hypotheses, each naming the observation
that would exclude it, plus a `predict_refusal` commitment. Refusals are
then booked against ground-truth labels, not vibes:

- **correct-restraint** — predicted restraint on a clean exercise
- **missed-bug** — restraint on an exercise with planted bugs
- **abstention** — restraint or silence WITHOUT a prior commitment
  (a refusal only counts as restraint when the receipt shows it was
  predicted; unpredicated silence is abstention, and the difference
  between a gate and a vibe is the booking)

Surviving hypotheses are corroborated, never "confirmed" — that is the
strong-inference part. Rows seal as hash-chained PREREG/v1 with the same
corpus binding and tamper behavior as EVAL/v1.

## Usage

```bash
pip install -e .
moth-honest plant --lang c -o /tmp/exercises   # materialize ground truth
moth-honest evaluate --report r.json -o eval.jsonl
moth-honest verify eval.jsonl
```

Report format:

```json
{
  "hunter_id": "my-hunter",
  "claims": [{"exercise_id": "c-overflow-001", "file": "main.c",
              "line": 7, "bug_class": "buffer_overflow", "confidence_q16": 32768}],
  "refusals": [{"exercise_id": "c-clean-001", "note": "snprintf bounded copy seen"}]
}
```

## The mock hunter

`examples/mock_hunter.py` is deliberately mediocre: 3 claims (1 true, 1 false
positive on clean code, 1 line near-miss inside tolerance), 1 explicit refusal,
silence elsewhere. Its sealed receipt ships in-repo
(`examples/mock_hunter.eval.jsonl`) and its honest score is:

```
P=0.6667 R=0.5000 F1=0.5714 (TP=2 FP=1 FN=2 refusals=1)
```

If a real hunter wants fleet trust, it beats this receipt with fewer claims.

## Family position

```
moth-ledger    envelopes + chain law + verify          (shipped, main @ e95c786)
moth-corpus    CorpusIndex: repos → receipted surface  (PR #1, awaiting merge)
moth-honest    the evaluator: planted truth, honest cost (this repo)
moth-cells     kernel 1: cellular predation            (next)
moth-runner    campaigns, witness.jsonl, throttle seam (after cells)
```

## Doctrine

- Numbers are re-derived, never trusted.
- A false positive is never deleted; clean exercises exist to catch them.
- Silence is not refusal — book the refusal or be counted a rumor mill.
- Stdlib only. No dependencies. Q16 everywhere.
- Chain law: caught lies are the only lies that matter.

## Tests

60 green. Receipt integrity, tamper/insert detection, corpus binding,
evaluation semantics, CLI roundtrip, Q16 pins, pre-registration labels:

```bash
python -m pytest
```
