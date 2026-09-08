# POL-01 — Authorization Policy Identity v1

Status: `CLOSED / ENGINEERING PASS` closure record for the final repaired POL-01 line.
Authority: Enterprise authorization policy identity/provenance only
Base measured: `main @ b7f2cc9abb078bfb5049282cf4f5d30e11517230`
Initial code implementation PR: `#186`
Initial code implementation merge: `1465bbbaade70346c5894b43d9261885c8d53614`
Final repaired implementation/closure-target PR: `#187`
Validated final exact head: `e1eadfdd1f2fc4ab3424c50c92ba147113ca6141`
Guarded final implementation merge: `63d0114bbd49b78ed71e337c1a7c8c0de72e0811`
Generated closure PR: `#188`
Next approved stage: `XCH-02`

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

The initial authorization-policy implementation merged through PR #186. Its post-merge
validation exposed a governance gap rather than a Product/security defect: the canonical
closure target still contained the disabled OPR-01 target. POL-01 was therefore not declared
closed. Repair PR #187 armed the canonical POL-01 target, was validated on a fresh exact head,
and was merged guardedly. Closure evidence was then regenerated from that repair merge rather
than reusing the earlier line. No PASS evidence was mixed across the two candidate SHAs.

## Exact closure record

The final repaired POL-01 line is bound to live GitHub evidence rather than chat or memory:

- final repaired implementation/closure-target PR: `#187`;
- validated exact final head:
  `e1eadfdd1f2fc4ab3424c50c92ba147113ca6141`;
- guarded final implementation merge:
  `63d0114bbd49b78ed71e337c1a7c8c0de72e0811`;
- merge parents:
  `1465bbbaade70346c5894b43d9261885c8d53614` and
  `e1eadfdd1f2fc4ab3424c50c92ba147113ca6141`;
- the exact final head passed all 15 required PR-triggered workflows;
- post-merge evidence records 13 terminal successful workflows, including CI Foundation,
  Enterprise CodeQL, Enterprise Hardcore Gate, FIV-02, SSC-02, OPR-01, Stage Gate,
  Production Validation, GitHub App Smoke Test and the `MVROS v1 Release` guard;
- Governance Closure PR Preparation run `34262_237223` generated closure PR `#188`
  (underscore is a display separator for the repository PII gate);
- machine evidence path:
  `evidence/governance_closure/pol-01/63d0114bbd49b78ed71e337c1a7c8c0de72e0811.json`;
- machine evidence identity:
  `3189b5ee96f90fc6a50296f8cde1c83a17690225384c1b708e5c64efc4948208`;
- governance live snapshot identity:
  `0a7d066c347b8446cea6fc061b09145019a344c8ed062608fd083d132439f3c1`;
- governance report identity:
  `4a48eeadd2546821fb79c0634ffd3d55655ab45f72aaf6c7eec7bbf473ae220a`;
- historical `v1.0.1` annotated tag object remained
  `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- immutable tag target remained
  `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- latest release remained `v1.0.1`;
- next approved stage is `XCH-02`.

The generated machine evidence deliberately remains `PREPARED_NOT_CLOSED` with
`closure-preparation-only` authority. It does not grant merge, release, Product, CCL, Gold,
certification or independent-review authority. This document becomes the canonical POL-01
closure record only after PR #188 itself passes complete exact-head validation, guarded merge,
resulting-main validation and immutable baseline/release verification. Engineering closure
does not claim independent external, regulatory or security certification.

## Acceptance criteria

POL-01 closure requires:

1. deterministic policy identity independent of caller role ordering;
2. canonical snapshot round-trip with exact engine reconstruction;
3. policy digest changes for material role-policy changes;
4. enforcement semantics are part of the canonical identity;
5. unknown/tampered/non-canonical snapshots fail closed;
6. existing tenant/scope/classification/trust-promotion behavior remains regression-covered;
7. focused, adversarial and full regression validation;
8. lint, strict typing, security/policy gates and exact-SHA CI;
9. guarded unchanged-head merge plus post-merge validation;
10. immutable baseline/release identity remains unchanged and no review is fabricated.
