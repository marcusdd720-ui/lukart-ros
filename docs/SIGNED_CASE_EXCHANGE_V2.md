# XCH-02 — Signed Case Exchange v2 / Portable Authorization Verification

Status: implementation candidate
Authority: transport/provenance verification only
Measured base: `main @ d7f6ff86310d0ecc0ca7b316d1c4f91712402418`
Depends on: `XCH-01 CLOSED / ENGINEERING PASS`, `POL-01 CLOSED / ENGINEERING PASS`

## Problem

XCH-01 already carries a fully signed, offline-verifiable Case Replay v2 exchange envelope and
binds source `case:read` plus recipient `case:write` authorization receipts. Those receipts
contain exact `context_digest` and `policy_digest`, but not the policy/context preimages.

After POL-01, authorization policy semantics are content-addressed and reconstructable, but an
XCH-01 recipient still cannot independently recompute the historical authorization decision
from envelope bytes alone because the original roles and bounded case/workspace scope are not
portable.

## Evidence

The measured gap is confined to authorization portability:

- `core/case_exchange_v1.py` signs the exact authorization receipt containing
  `context_digest`, `policy_digest`, `decision_digest`, resource identity and request binding;
- `core/enterprise/authorization_policy.py` provides canonical `AuthorizationPolicyV1` and
  exact `AuthorizationEngine.from_policy()` reconstruction;
- `AuthorizationContext.digest()` binds subject, tenant, roles, derived permissions and bounded
  case/workspace scope;
- XCH-01 verification already proves replay integrity, request/scope binding and attestation.

No new CCL/import/signature authority is required.

## Decision

XCH-02 is a versioned portability wrapper over the complete signed XCH-01 envelope.

It adds exactly two portable authorization proofs, source and recipient. Each proof contains:

- the exact canonical `AuthorizationPolicyV1` snapshot;
- minimal historical context preimage: subject, tenant, roles, case IDs and workspace IDs;
- a content-addressed proof identity.

Permissions are intentionally **not** accepted as portable input. They are re-derived from the
exact policy and roles by the existing `AuthorizationEngine`.

The XCH-02 wrapper itself is content-addressed. It does not add a second signature because the
embedded XCH-01 signature already binds the authorization receipt's policy/context digests.
The added proof bytes are accepted only when they reproduce those signed digests and the exact
signed decision.

## Offline verification sequence

1. Strictly parse the XCH-02 schema and reject unknown fields.
2. Verify the embedded XCH-01 envelope with the existing verifier.
3. Parse the exact source and recipient policy snapshots.
4. Rebuild each authorization context from policy + minimal context preimage.
5. Require rebuilt context digest to equal the signed XCH-01 `context_digest`.
6. Require policy digest to equal the signed XCH-01 `policy_digest`.
7. Re-run the existing `AuthorizationEngine.decide(..., strict_scope=True)` against the signed
   request/resource.
8. Require the recomputed decision to be allowed and its digest to equal the signed
   `decision_digest`.
9. Verify each proof identity and complete XCH-02 content identity.

A modified proof with a freshly recomputed wrapper hash still fails unless it is the exact
preimage of the policy/context digests already protected by the XCH-01 signature.

## Fail-closed boundary

XCH-02 rejects:

- unknown/missing v2 fields;
- unknown policy/context/proof schemas;
- policy digest substitution;
- role, tenant, case or workspace context substitution;
- non-canonical context ordering/duplication;
- source/recipient proof swapping;
- historical decision recomputation mismatch;
- any inner XCH-01 replay/request/authorization/signature failure;
- expired or otherwise invalid XCH-01 attestation.

## Trust boundary

XCH-02 does **not**:

- write or restore Canonical Case Ledger data;
- authorize import, merge, overwrite or fork of a target case;
- promote FACT/TRUST or reinterpret Gold;
- make attestation evidence into epistemic truth;
- embed a self-trusted public key or create a new trust root;
- replace XCH-01, AuthorizationEngine, Case Replay v2 or POL-01 policy identity;
- claim human, independent, regulatory or external security certification.

Trusted verification keys remain explicit verifier input, not self-asserted envelope data.

## Compatibility

The complete XCH-01 signed envelope is preserved byte-semantically inside XCH-02. Existing
XCH-01 verification therefore remains valid and independently exercisable. Historical XCH-01
artifacts are not silently upgraded; XCH-02 is a new explicit wrapper schema.

## Acceptance criteria

XCH-02 closure requires:

1. exact XCH-01 verification remains unchanged and required;
2. source and recipient policy/context preimages reproduce their signed digests;
3. both authorization decisions are independently recomputed offline using the existing
   engine and exact historical policy;
4. tampered policy/context/proof bytes fail even if wrapper/proof hashes are recomputed;
5. unknown schemas/fields and non-canonical input fail closed;
6. no CCL write/import/merge, Gold, release or trust-promotion authority is introduced;
7. deterministic exact-input XCH-02 identity;
8. focused/adversarial/full regression, Ruff, strict MyPy and security/policy gates pass on one
   exact candidate SHA;
9. guarded exact-head merge and resulting-main validation complete;
10. immutable `v1.0.1` tag/release identity remains unchanged.
