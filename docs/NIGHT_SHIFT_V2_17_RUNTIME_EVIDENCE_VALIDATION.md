# Night Shift V2-17 — Runtime Evidence Validation Boundary

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

V2-17 defines the fail-closed boundary between complete V2-16 runtime evidence
and a proposal that may proceed to a separately signed runtime-matrix change.

Canonical flow:

`V2-16 acquisition -> exact acquisition digest -> exact repository SHA -> trusted SECURITY_REVIEW attestations -> READY_FOR_SIGNED_MATRIX_CHANGE or BLOCKED`

The gate validates review evidence. It does not mutate the runtime matrix.

## Cryptographic review requirements

- candidates remain exactly DBOS and Temporal;
- source profiles must remain DOCUMENTED;
- V2-16 acquisition must be READY_FOR_HUMAN_VALIDATION;
- acquisition and candidate digests are bound exactly;
- source profile digest is bound exactly;
- repository identity is a lowercase 40-character Git SHA;
- trust-set identity is pinned;
- reviewer keys must be trusted for SECURITY_REVIEW;
- builder identity is bound into every signed review payload;
- a builder cannot self-certify as the runtime evidence reviewer;
- review signatures must verify under the pinned trust set;
- expired, tampered or stale reviews fail closed;
- at least two distinct reviewer key identities are required per runtime;
- the two-review threshold cannot be lowered by caller policy;
- duplicate reviewer identities never increase quorum.

## Authority boundary

`READY_FOR_SIGNED_MATRIX_CHANGE` is not VALIDATED runtime state.

It means only that the exact acquisition package has enough cryptographically
verified review evidence to prepare a separate signed matrix-change proposal.

V2-17 does not:

- change `RuntimeProfile.evidence`;
- write `NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml`;
- install or select DBOS or Temporal;
- increase runtime or publication authority;
- certify a runtime for production;
- enable unattended production publication.

## Current expected state

The canonical matrix still contains `future_dbos_adapter` and
`future_temporal_adapter`. Therefore the real current chain remains BLOCKED
before signed matrix-change readiness. Tests may construct isolated concrete
fixtures only to prove the gate semantics.

A later separately reviewed and signed commit is required to change any
canonical runtime profile from DOCUMENTED to VALIDATED.

Evidence Before Conclusion.
Planned != Implemented != Validated != Certified.
Factory != Product.
