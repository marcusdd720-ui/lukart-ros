# KMS-1.0 — Kanon Modelu Sprawy

Canonical ID: KMS-1.0
Title: Kanon Modelu Sprawy
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Case Architecture
Depends On: KMeta-1.0; CK-1.0; KMR-1.0; TM-1.0; KCS-1.2
Affects: KMP; Evidence; Reasoning; Decision; Strategy; Renderer; Case Replay
Supersedes: none
Validation Method: model mapping + synthetic case construction + replay + scope tests
Review Requirement: independent architectural review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KMS-1.0 defines the Model Sprawy as a bounded, versioned projection of the broader cognitive model under one Case scope. It answers: `Which fragment of reality and knowledge is relevant to this Case?`

## 2. Definition

`CaseModel = <case_id, scope_version, object_refs, relation_refs, source_refs, temporal_view, unresolved_items, model_version, lineage>`

The Case Model is a projection/reference structure, not an uncontrolled copy of all globally known objects.

## 3. Inputs

A Case Model may consume only material admitted by the Case ScopePolicy and ReferenceSet, including:

- cognitive objects,
- relations,
- source references,
- approved cross-case references,
- explicit open questions,
- temporal constraints.

## 4. Exclusions

The Case Model MUST NOT contain material solely because it exists in global knowledge. Inclusion requires Case relevance and authorization.

## 5. Model semantics

The Case Model preserves object-level epistemic state and provenance from KMR. It MUST NOT flatten FACT/CLAIM/HYPOTHESIS/UNKNOWN distinctions into a single case-level truth list.

## 6. Temporal view

The Case Model provides a temporally coherent view using TM semantics. It may expose:

- current-known view,
- historical knowledge-time view,
- event-time ordered projection,
- source-time projection.

The requested view MUST be explicit where temporal differences are material.

## 7. Open questions

Unresolved knowledge needs relevant to the Case are first-class references in the Case Model. They are not hidden merely because no source currently resolves them.

## 8. Contradictions

Contradictions are preserved as explicit relations/assessment artifacts. KMS does not resolve them by majority count or model preference.

## 9. Versioning

Every material change in admitted references, scope, relevant object versions or temporal interpretation produces a new Case Model version or auditable Change Set.

## 10. Projection rules

Projection from broader knowledge into a Case Model MUST preserve:

- identity,
- epistemic state,
- provenance,
- authorization/reference path,
- version lineage.

Projection MUST NOT silently strengthen epistemic status.

## 11. Separation from Problem Model

The Case Model describes the relevant state of knowledge. It does not decide which legal/decision problem is primary. Problem selection belongs to KMP.

The same Case Model may support multiple Problem Models.

## 12. Separation from Evidence assessment

KMS may reference evidence/source material, but evidentiary quality, completeness, admissibility/relevance and burden are assessed by the Evidence domain.

## 13. Separation from Strategy

The Case Model does not contain recommended actions or tactics as facts. Strategy is downstream and may be recomputed without mutating historical Case Model state.

## 14. Failure modes

Case Model construction/update MUST fail closed or remain incomplete when:

- Case scope/version is unavailable;
- reference authorization cannot be established;
- projection loses provenance or epistemic status;
- cross-case data has no approved reference path;
- a relevant contradiction is silently discarded;
- a requested historical view cannot be reconstructed.

## 15. Validation

KMS-1.0 remains Candidate until:

1. at least one synthetic Case is represented through KCS -> KMS;
2. current case/timeline/knowledge graph artifacts are mapped to KMS fields;
3. replay reconstructs at least two Case Model versions;
4. leakage tests prove out-of-scope material is excluded;
5. KMP consumes KMS without mutating it;
6. exact-SHA CI/Audit/Stage Gate passes;
7. independent review approves before CANONICAL.
