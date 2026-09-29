# Night Shift V2-22 — Runtime Shadow Activation Evidence

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

Evaluate evidence from bounded V2-21 shadow execution before any runtime can proceed
to promotion review.

## Fail-closed evidence floor

For each of DBOS and Temporal:

- minimum three globally unique shadow runs;
- exact V2-21 plan-candidate digest binding;
- side-effect-free execution;
- verified rollback;
- deterministic replay PASS;
- task budget respected;
- unique evidence digests;
- test/synthetic/demo evidence rejected.

READY_FOR_PROMOTION_REVIEW is advisory only. It does not promote, publish, or mutate
production state.
