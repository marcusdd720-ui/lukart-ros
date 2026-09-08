# POL-01 — Authorization Policy Identity v1

Status: implementation merged; canonical closure pending
Authority: Enterprise authorization policy identity/provenance only
Base measured: `main @ b7f2cc9abb078bfb5049282cf4f5d30e11517230`
Validated implementation head: `e1490b916499bcf9ef9d098b1773525a5d64b925`
Implementation PR: `#186`
Implementation merge: `1465bbbaade70346c5894b43d9261885c8d53614`

## Problem

`AuthorizationEngine.policy_digest()` previously hashed only role definitions. Runtime
authorization decisions also depended on tenant equality, case/workspace scope semantics,
data-classification ordering, deny-by-default behavior and the additional independent
`security:review` permission required for `trust:promote`. A behaviorally material policy
change in those enforcement semantics could therefore retain the same policy digest.

That is an identity/provenance gap. It does not invalidate historical XCH-01 signatures or
turn an authorization receipt into Product truth, but it prevents the digest alone from
binding the complete v1 authorization semantics needed for long-horizon audit and portable
offline verification.

## Evidence and measurement

Measured production surfaces:

- `core/enterprise/authorization.py` — existing E5/H6 decision authority and receipt digest;
- `core/case_exchange_v1.py` — XCH-01 carries signed authorization receipts containing an
  opaque `policy_digest` but no policy snapshot;
- `core/case_replay_v2.py` — replay already demonstrates the stronger pattern for exact,
  content-addressed policy identity and offline reconstruction;
- `knowledge/evidence_trust_graph.py` and `knowledge/epistemic_assertions.py` — existing trust
  and epistemic policies already bind canonical policy bodies to exact identities.

The smallest material gap is therefore authorization-policy identity, not a new policy
engine, policy database or parallel authority.

## Decision

POL-01 introduces `AuthorizationPolicyV1`, a deterministic content-addressed snapshot used by
the existing `AuthorizationEngine`.

The canonical policy body binds:

- exact role names, permissions and maximum data classification;
- deny-by-default semantics;
- exact tenant-match semantics;
- case and workspace `strict-or-bounded-context.v1` scope semantics;
- exact classification ordering;
- the additional `security:review` requirement for `trust:promote`;
- an explicit authorization-decision semantics identity.

`AuthorizationEngine.policy_digest()` is the digest of that canonical body. The engine can
return the exact snapshot and can be reconstructed from a verified snapshot without adding a
second authorization implementation.

## Fail-closed contract

`AuthorizationPolicyV1.from_dict()` rejects:

- unknown or missing fields;
- unknown schema or enum values;
- non-canonical role/permission ordering or duplication;
- modified enforcement semantics;
- digest/content mismatch.

A snapshot from an unsupported future schema is not implicitly treated as the current
policy. Migration or cross-version comparison requires a separately explicit contract.

## Compatibility

- Existing `AuthorizationDecision` schema and `policy_digest` field remain unchanged.
- Existing callers constructing `RoleDefinition` and `AuthorizationEngine` remain supported.
- Historical XCH-01 envelopes remain historical signed artifacts; POL-01 does not rewrite or
  silently reinterpret their opaque policy digests.
- A new policy body creates a new digest. Historical decisions remain tied to their historical
  digest instead of being retroactively re-authorized under current policy.

## Trust boundaries and non-goals

POL-01 does **not**:

- write Canonical Case Ledger state;
- promote FACT/TRUST or alter Gold;
- create a policy persistence authority, policy registry or generic policy language;
- add import/merge authority to signed case exchange;
- create an implicit migration path between policy schemas;
- claim independent human, security, regulatory or external certification.

## XCH-02 handoff

The next approved exchange stage may embed or otherwise bind the exact
`AuthorizationPolicyV1` snapshot needed to re-evaluate historical authorization receipts
offline. That portability work belongs to XCH-02; POL-01 only establishes the exact policy
identity and reconstruction primitive it requires.

## Closure repair provenance

The implementation PR and its exact merge passed the stage's implementation and post-merge
gates. During closure preparation, the canonical target remained the disabled OPR-01 target,
so the preparation workflow correctly performed no POL-01 closure mutation. POL-01 therefore
remains open until a fresh exact-SHA repair candidate arms the canonical closure target,
passes the full validation pipeline, merges, and generates closure evidence from that repair
merge. No earlier PASS is reused across the repair SHA.

## Acceptance criteria

POL-01 implementation closure requires:

1. deterministic policy identity independent of caller role ordering;
2. canonical snapshot round-trip with exact engine reconstruction;
3. policy digest changes for material role-policy changes;
4. enforcement semantics are part of the canonical identity;
5. unknown/tampered/non-canonical snapshots fail closed;
6. existing tenant/scope/classification/trust-promotion behavior remains regression-covered;
7. focused, adversarial and full regression validation;
8. lint, strict typing, security/policy gates and exact-SHA CI;
9. guarded unchanged-head merge plus post-merge validation;
10. no release/tag mutation and no fabricated independent review.
