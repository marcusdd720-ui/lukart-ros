# Night Shift V2-09 — Evidence-Bound Verification Quorum

Status: VALIDATED STAGING CANDIDATE  
Recorded: 2026-09-28

## Objective

Replace boolean-only promotion evidence with a content-addressed verification bundle bound to one exact candidate and one TaskCapsule.

V2-09 does not add cryptographic reviewer signatures. That authority belongs to V2-10.

## Required gates

Every quorum requires exactly one evidence record for each gate:

1. focused tests;
2. static security;
3. scope guard;
4. required regression;
5. independent review;
6. exact-SHA CI;
7. policy engine.

Missing or duplicate gate evidence fails closed.

## Evidence binding

Every VerificationEvidence record binds:

- gate identity;
- PASS/FAIL result;
- exact subject Git OID;
- TaskCapsule digest;
- producer identity;
- observation time;
- content digest of the underlying evidence;
- one or more evidence references.

A VerificationBundle rejects mixed SHAs and mixed TaskCapsules.

The independent-review evidence producer must equal the declared reviewer identity, and the builder and reviewer identities must differ.

## Promotion binding

VerificationQuorum now carries:

- subject SHA;
- TaskCapsule digest;
- aggregate evidence digest;
- builder identity;
- reviewer identity;
- the seven gate results.

decide_promotion requires the caller's expected subject SHA and TaskCapsule digest and rejects a quorum bound to anything else.

Therefore a PASS collected for one candidate cannot be replayed for another candidate or another task.

## Freshness and replay boundary

Exact-SHA binding alone is not sufficient because operational evidence can become stale even when the candidate SHA and TaskCapsule remain unchanged.

V2-09 therefore applies a bounded evidence lifetime:

- profile-controlled maximum evidence age: 3600 seconds;
- evidence observed in the future is blocked;
- expired evidence is blocked during quorum assembly;
- promotion rechecks the quorum evidence expiry at decision time;
- the calculated evidence-valid-until timestamp is included in the quorum digest.

This prevents a previously valid CI/reviewer/security bundle from being replayed indefinitely under a later autonomy envelope.

## Receipt binding

ExecutionReceipt already binds verification_digest. V2-09 makes that digest transitively cover the evidence bundle, exact candidate and TaskCapsule.

## V2-10 boundary

V2-09 establishes evidence and identity binding but does not prove possession of a signing key by the evidence producer.

Cryptographic automation identity and receipt signing remain V2-10.

Planned != Implemented != Validated != Certified.  
Evidence Before Conclusion.


## Validation evidence

Local validation before staging freeze:

- focused V2-09 verification/promotion/canary tests: PASS;
- future-evidence rejection regression: PASS;
- expired-evidence rejection regression: PASS;
- promotion-time evidence expiry regression: PASS;
- full Night Shift test set: PASS across 32 test files;
- Ruff: PASS;
- Mypy Linux target: PASS across 859 source files;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS;
- controlled canary integration after quorum binding: PASS.
