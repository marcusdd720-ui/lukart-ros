# KCS-1.2 — Kanon Czym Jest Sprawa

Canonical ID: KCS-1.2
Title: Kanon Czym Jest Sprawa
Version: 1.2
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Case Architecture
Depends On: KMeta-1.0; CK-1.0; KMR-1.0; TM-1.0; FOUNDATION.md
Affects: KMS; KMP; Evidence; Reasoning; Strategy; Execution; Privacy Boundary
Supersedes: KCS-1.1 conceptual draft
Validation Method: scope-isolation tests + private-pilot mapping + adversarial cross-case tests
Review Requirement: independent architectural/privacy review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KCS-1.2 defines a Case as a bounded cognitive work context. A Case is not a folder and not a document collection. Its primary role is to constrain attention, authority, evidence visibility and reasoning scope so that Artur OS does not attempt to reconcile every task with all available knowledge.

## 2. Locality principle

Every analytical and decision process MUST execute under an explicit finite Case scope unless a higher-level operation is explicitly defined as cross-case/global.

A Case boundary is a cognitive and privacy boundary, not merely an organizational label.

## 3. Formal Case definition

A Case is the tuple:

`SP = <case_id, scope_policy, reference_set, ownership, operational_state, epistemic_state, goals, model_ref, version>`

Where:

- `case_id` — stable Case identity;
- `scope_policy` — rules defining what may enter, remain in, or leave Case scope;
- `reference_set` — explicit references available to the Case;
- `ownership` — accountable owner/authority context;
- `operational_state` — workflow state;
- `epistemic_state` — state of knowledge readiness/quality, separate from workflow;
- `goals` — declared purposes/decision needs for the Case;
- `model_ref` — reference to current Model Sprawy version;
- `version` — immutable Case-definition version.

## 4. ScopePolicy

`ScopePolicy` MUST define at least:

- inclusion criteria,
- exclusion criteria,
- privacy/confidentiality restrictions,
- permitted source classes,
- temporal bounds where material,
- subject/entity bounds where material,
- cross-case reference policy,
- escalation rules for ambiguous relevance.

ScopePolicy MUST be auditable and versioned.

## 5. ReferenceSet

`ReferenceSet` contains authorized references to source material, cognitive objects, external authorities or explicitly imported cross-case references.

ReferenceSet MUST NOT be interpreted as copying all referenced content into Case ownership.

Each reference SHOULD include:

- reference identity,
- reference type,
- source/target identity,
- visibility/authorization state,
- provenance/integrity identity,
- reason for relevance,
- inclusion timestamp/version.

## 6. No embedded Bridges

Inter-case bridges are not intrinsic fields of the Case model. Cross-case relationships are governed by a separate Case Bridge contract.

KCS therefore does not grant Case A direct access to Case B merely because a relationship exists.

## 7. Ownership

A Case MUST have a single accountable owner context for scope and lifecycle decisions. Ownership does not imply unrestricted access to every source related to the owner/client.

Where legal/professional roles require separation, access authority MUST be represented separately from factual identity.

## 8. Operational state vs epistemic state

Operational state and epistemic state MUST NOT be conflated.

Examples of operational states:

- INTAKE
- COLLECTING
- ANALYSIS
- DECISION_PREPARATION
- ACTION
- MONITORING
- CLOSED
- ARCHIVED

Examples of Case-level epistemic readiness assessments:

- INSUFFICIENT_EVIDENCE
- MATERIAL_CONTRADICTION
- OPEN_QUESTIONS
- ANALYTICALLY_READY
- DECISION_READY

These Case-level assessments are derived from underlying model/evidence state and do not replace object-level epistemic status.

## 9. Goals

Goals express why a Case exists and what decision need is being pursued. A goal is not a document-generation instruction by default.

Example decomposition:

`Protect client against claim` -> `determine legal/factual problem` -> `select strategy` -> `plan action` -> `render communication if needed`.

A Case MAY have multiple goals, but each active goal MUST be explicit and versioned.

## 10. Cognitive firewall

Reasoning executing under Case A MUST NOT directly enumerate or query private Case B material outside authorized references.

A cross-case discovery candidate MUST be exported as a proposed reference/bridge event and evaluated under the Case Bridge policy before Case B can consume it.

## 11. Relevance admission

A new source/object may enter Case scope only through an explicit admission decision based on at least one of:

- direct goal relevance,
- entity/topology relevance,
- temporal relevance,
- evidentiary relevance,
- legal/procedural relevance,
- explicit human inclusion.

Admission may remain PENDING when relevance is uncertain.

## 12. Case closure

Case closure is not defined as mathematical `Dist(model, goal) = 0` because many legal and real-world matters end with residual uncertainty.

A Case may become CLOSED only when:

- active goals are resolved, withdrawn, superseded or explicitly accepted as unresolved;
- required actions are completed or transferred;
- open questions are classified as non-blocking or preserved for monitoring;
- closure reason and authority are recorded.

CLOSED does not erase the Case model. It freezes the operational snapshot and preserves replay history.

## 13. Reopening

A closed Case may be reopened by a new version when new evidence, new proceeding, new goal or changed reality makes renewed work necessary. Reopening MUST preserve prior closure state and history.

## 14. Failure modes

Case operations MUST fail closed or remain pending when:

- ScopePolicy is absent for a sensitive Case;
- ownership/authority is ambiguous;
- a reference would bypass privacy boundary;
- cross-case content is consumed without approved reference/bridge semantics;
- operational state is used as proof of epistemic readiness;
- closure would discard material unresolved obligations;
- Case scope expands recursively without bounded relevance rules.

## 15. Validation

KCS-1.2 remains Candidate until:

1. existing `Case`, `case_manager`, `local_case_store` and private-pilot behavior are mapped to its fields;
2. tests demonstrate Cognitive Firewall and explicit ReferenceSet admission;
3. adversarial cross-case leakage tests fail closed;
4. KMS and KMP use Case scope without duplicating its semantics;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent architectural/privacy review approves before CANONICAL.
