# KCB-1.0 — Kanon Case Bridge

Canonical ID: KCB-1.0
Title: Kanon Case Bridge
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Case Architecture
Depends On: KMeta-1.0; CK-1.0; KMR-1.0; KCS-1.2; KMS-1.0
Affects: Privacy Boundary; Evidence; Reasoning; Audit; Case Replay
Supersedes: embedded Bridges concept from KCS-1.1
Validation Method: adversarial cross-case transfer tests + authorization/audit tests
Review Requirement: independent architectural/privacy review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KCB-1.0 defines controlled, auditable transfer/reference semantics between isolated Cases without weakening the Cognitive Firewall.

## 2. Bridge is not direct Case access

A Case Bridge never grants Case A general query access to Case B. It authorizes a specific bounded reference or disclosure under explicit policy.

## 3. Definition

`CaseBridge = <bridge_id, source_case_ref, target_case_ref, subject_refs, disclosure_level, purpose, authorization, provenance, status, created_at, version, audit_lineage>`

## 4. Subject references

`subject_refs` SHOULD point to stable cognitive/source identities rather than duplicating arbitrary content.

A bridge may disclose:

- metadata only,
- a bounded derived reference,
- a specific source/object version,
- a redacted representation,
- full content only when policy/authorization permits.

## 5. Lifecycle

Allowed states:

- PROPOSED
- REVIEW_REQUIRED
- APPROVED
- REJECTED
- ACTIVE
- REVOKED
- EXPIRED
- ARCHIVED

A proposed bridge MUST NOT be consumable by the target Case until approval requirements are met.

## 6. Authorization

Authorization MUST record the applicable authority context. Same client identity across two Cases does not automatically authorize full disclosure.

Rules may consider:

- privacy/confidentiality,
- conflict of interest,
- professional secrecy,
- purpose limitation,
- human approval requirement,
- legal/compliance restrictions.

## 7. Candidate discovery

A Case may emit a cross-case relevance candidate without revealing protected content. The candidate SHOULD contain the minimum information necessary to evaluate whether a bridge should be reviewed.

## 8. Imported semantics

Material imported into a target Case enters through its ReferenceSet and normal admission/update contracts.

Imported material MUST preserve:

- original identity/version,
- provenance,
- source Case/bridge path,
- disclosure limitations,
- epistemic status.

Import MUST NOT promote epistemic state solely because another Case had previously accepted the material.

## 9. Revocation

Revocation stops future authorized access where technically/legal possible but MUST NOT destroy historical audit records proving that access previously occurred.

If a downstream decision relied on later-revoked material, the system SHOULD emit a change-propagation event for review.

## 10. No combinatorial Case graph requirement

KCB permits bridges only where actual cross-case relevance exists. Global cognitive objects may be referenced by multiple Cases without creating pairwise bridges when no cross-case disclosure is occurring.

## 11. Failure modes

Bridge activation MUST fail closed when:

- source/target Case identity is ambiguous;
- authorization is missing;
- disclosure exceeds declared purpose/level;
- subject version/provenance is missing;
- target scope policy rejects the reference;
- protected content is exposed at candidate-discovery stage;
- automation attempts self-approval where human review is required.

## 12. Validation

KCB-1.0 remains Candidate until:

1. adversarial tests prove no direct Case-to-Case enumeration;
2. metadata-only candidate discovery avoids protected-content leakage;
3. approved bridge imports through target ReferenceSet rather than bypassing it;
4. revoked bridge produces auditable history and propagation signal;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent privacy/architectural review approves before CANONICAL.
