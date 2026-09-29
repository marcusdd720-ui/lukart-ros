# Night Shift V2-23 — Runtime Promotion Readiness

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

Convert validated V2-22 shadow evidence into a human promotion decision package.

This stage cannot promote DBOS or Temporal. It only reports whether the evidence is
complete enough for a human promotion decision.

## Fail-closed review floor

For each runtime:

- exact V2-22 shadow candidate digest binding;
- minimum two distinct cryptographic reviewer identities;
- every review is a SECURITY_REVIEW attestation under the pinned trust set;
- reviewer identity must differ from builder identity;
- every signed review must explicitly APPROVE;
- tampering with approval or evidence invalidates signature verification.

## Authority boundary

- automatic promotion disabled;
- registry mutation disabled;
- runtime matrix mutation disabled;
- production publication disabled;
- READY_FOR_HUMAN_PROMOTION_DECISION is not promotion or certification.

Human authority remains required for any future production runtime change.
