# PHX-03 — Epistemic Assertion + State Machine v2

Status: Active engineering contract
Baseline: `main @ a0fa7e128366bc26419ae820d3ce88691a55723a`
Authority: Canonical Case Ledger only

## Problem

The legacy `EpistemicStatusMachine` correctly denies unknown transition shapes, but its
`evidence_refs` contract accepts arbitrary nonblank strings. `CaseScope` also carried a
coarse epistemic state that could be changed by replacement. Neither property is strong
enough for the Post-Hardcore trust chain, where FACT promotion and every authoritative
state transition must be bound to exact immutable case history.

## Alternatives considered

### A. Harden legacy fields only

Add stricter strings/hashes to `CaseScope` and the old transition request. Rejected as the
primary design because it leaves object/scope state as a competing writable authority and
cannot deterministically reconstruct state from complete case history.

### B. Immutable Assertion + transition events in Canonical Case Ledger

Create content-addressed Assertions, exact evidence-event references, versioned policy and
content-addressed transition decisions. Rebuild state as a deterministic projection over
CCL events. Selected because it preserves the existing CCL SSOT, requires no new database,
provides exact replay/provenance, and keeps transition policy small and testable.

### C. Dedicated epistemic event store

Rejected because it creates a second authoritative persistence/history system and requires
cross-store transaction/reconciliation semantics without evidence that the complexity is
needed.

### D. General-purpose event-sourcing framework

Rejected for PHX-03. It could solve broader problems but introduces framework/migration and
operational cost without a current failure mode that justifies it.

Decision: **B — smallest design that closes the measured trust boundary.**

## Canonical model

Authoritative epistemic history consists only of CCL events:

- `epistemic.assertion.created.v1`
- `epistemic.assertion.transition.v1`

An Assertion is immutable and content-addressed. It binds:

- exact Case ID;
- exact logical subject Object ID;
- versioned assertion type;
- canonical assertion content;
- initial epistemic status;
- exact prior CCL evidence-event references;
- exact policy identity.

A transition decision is also immutable/content-addressed and binds:

- assertion identity;
- source and target statuses;
- exact prior evidence-event references;
- rationale;
- exact policy identity;
- allowed/denied result and reason.

Denied decisions are never appended as authoritative state transitions.

## Evidence contract

PHX-03 does not treat a nonblank string, URL, filename, model output or arbitrary event as
sufficient FACT evidence.

An evidence reference contains exact `case_id + CCL event_id`. For FACT creation/promotion:

1. the referenced event must already exist before the assertion/transition event;
2. the reference must resolve in the same Case;
3. its event type must be explicitly authorized by the versioned epistemic policy;
4. current v2 reference policy accepts `evidence.ingested.v1` for FACT support;
5. unknown, future or cross-case evidence fails closed until an explicit trust contract is
   versioned and implemented.

Changing allowed evidence types changes policy identity.

## Policy identity

`EpistemicPolicyV2` content-addresses:

- the deterministic legacy transition-policy document;
- authorized FACT evidence event types;
- the rule that CCL is the authoritative state source;
- the rule that canonical same-state transitions are rejected.

The existing transition machine therefore remains the single transition-shape policy
implementation; PHX-03 adds exact reference resolution rather than duplicating its rule set.

## Projection

`EpistemicProjectionV2` is a deterministic read model over verified CCL history. It:

- applies assertions/transitions in ledger order;
- rejects duplicate assertions;
- verifies exact policy identity;
- re-resolves evidence against prior events;
- recomputes transition policy rather than trusting recorded `allowed` blindly;
- rejects source-state mismatch;
- rejects denied/no-op/unknown epistemic events;
- binds its identity to exact ledger head, policy and projected assertion states.

The projection has no persistence/write API and can be rebuilt from history.

## Legacy boundary

`CaseScope.epistemic_state` remains temporarily for backward-compatible coarse snapshots,
but it is explicitly non-authoritative. `CaseScope.with_states()` can still change
operational state but rejects attempts to change the legacy epistemic field. New code must
consume PHX-03 projection state instead.

The legacy `EpistemicStatusMachine` remains available for compatibility/validation and is
explicitly documented as non-authoritative. Authoritative changes use
`EpistemicLedgerService`, whose only write operation terminates in `CanonicalCaseLedger`.

## Failure modes closed

PHX-03 explicitly tests/rejects:

- arbitrary/fake evidence identity;
- non-evidence event used for FACT promotion;
- cross-case evidence without trust contract;
- stale CCL head;
- no-op canonical transition;
- manually injected policy-violating transition;
- unknown epistemic event type;
- competing CaseScope epistemic mutation;
- policy/state mismatch during replay.

## Long-horizon boundary

PHX-03 intentionally does not implement cross-case evidence trust, signed trust scoring,
Trust Graph, replay package v2 or semantic invalidation. Those depend on the exact
Assertion/evidence identities created here and are subsequent Post-Hardcore stages.

Unknown future schema/event/policy remains FAIL rather than being guessed.

## Closure

Engineering closure requires focused/adversarial tests, full regression, lint/type-check,
security/policy gates, complete exact-SHA CI, guarded merge and exact resulting-main
post-merge validation. Automated PASS is not independent external certification.
