# Reasoning KQM Status — v1.0

## Current state: TECHNICAL BASELINE VERIFIED / PRODUCTION CERTIFICATION BLOCKED

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

## Verified contract-conformance baseline

Measured on validated feature SHA:

`d8406f4c4edc5ec457228a5bead2efa3bacbb826`

### Development — 4 cases

- decision accuracy: `1.0`
- valid-conclusion recall: `1.0`
- abstention recall: `1.0`
- unsafe-conclusion rate: `0.0`
- Open Question coverage: `1.0`
- evaluation failures: `0`

### Validation — 2 cases

- decision accuracy: `1.0`
- valid-conclusion recall: `1.0`
- abstention recall: `1.0`
- unsafe-conclusion rate: `0.0`
- Open Question coverage: `1.0`
- evaluation failures: `0`

### Locked evaluation

- executed: **NO**
- status: **UNTOUCHED / PROTECTED**

The baseline was accepted only after CI Foundation passed on Python 3.11, 3.12 and 3.13,
Architectural Audit passed, and GitHub App Smoke Test passed on the exact feature SHA.

## Interpretation boundary

This is a **technical contract-conformance baseline**, not production or legal reasoning
certification. The candidate contains a small number of synthetic cases chosen to test explicit
reasoning invariants such as evidence-backed conclusions, abstention, missing support, UNKNOWN,
and UNRESOLVED states.

A perfect score here proves that the current deterministic engine behaves consistently with the
encoded synthetic contract. It does not prove that real-world conclusions are legally or
factually correct across representative domains.

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
