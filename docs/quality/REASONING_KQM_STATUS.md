# Reasoning KQM Status — v1.0

## Current state: TECHNICAL MEASUREMENT PATH IMPLEMENTED / FIRST BASELINE PENDING

P3 introduces a separate reasoning benchmark path:

`Reasoning Gold Candidate -> ReasoningEngine -> ReasoningRunResult -> Reasoning KQM -> Failure Records`

This benchmark is independent of the existing extraction benchmark. No extraction Gold data,
threshold, locked split, or ReferenceFactAgent certification state is modified by P3.

## Candidate corpus

- Corpus: `reasoning-gold-v1`
- Version: `1.0.0`
- Status: `candidate_pending_independent_review`
- Review status: `not_reviewed`
- Development: 4 synthetic cases
- Validation: 2 synthetic cases
- Locked evaluation: 2 synthetic cases

The locked reasoning split is not authorized for P3 development/validation and is protected by
a fail-closed API.

## Metrics

The technical evaluator records:

- decision accuracy;
- valid-conclusion recall;
- abstention recall;
- unsafe-conclusion rate;
- Open Question coverage;
- per-case deterministic result digests;
- explicit failure records.

## Interpretation boundary

The first candidate is primarily a contract-conformance benchmark. Even a perfect result on
this small synthetic corpus would prove deterministic behavior against the encoded contract,
not production/legal reasoning correctness.

Production reasoning certification remains BLOCKED until at least:

1. independent review of corpus labels and expected outcomes;
2. corpus freeze/versioning under an approved reasoning Gold protocol;
3. broader domain-representative synthetic or approved local-only benchmark cases;
4. explicit certification thresholds justified by measured risk;
5. regression testing across engine versions;
6. separately authorized locked evaluation.

## Locked split policy

The locked split must not be executed for implementation tuning, rule selection, threshold
selection, or error-driven corpus changes. P3 tests verify that an unauthorized locked request
raises `LockedReasoningEvaluationError`.

Measured development/validation results will be recorded here only after the corresponding
fresh SHA passes the repository quality gates.
