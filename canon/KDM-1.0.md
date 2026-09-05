# KDM-1.0 — Kanon Modelu Decyzji

Canonical ID: KDM-1.0
Title: Kanon Modelu Decyzji
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Decision Architecture
Depends On: KMeta-1.0; CK-1.0; KMS-1.0; KMP-1.0; KEV-1.0
Affects: Strategy; Planning; Renderer; Audit; Case Replay
Supersedes: none
Validation Method: option-comparison tests + abstention tests + decision replay
Review Requirement: independent architectural/domain review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KDM-1.0 defines the Decision Model that records why Artur OS or an authorized human selected, rejected, deferred or abstained from a course of action.

## 2. Definition

`DecisionModel = <decision_id, problem_ref, case_model_ref, evidence_assessment_refs, options, constraints, assumptions, risks, rejected_options, selected_option, rationale, authority, status, version, lineage>`

## 3. Decision states

Allowed high-level states include:

- PROPOSED
- DEFERRED
- ABSTAIN
- SELECTED
- REJECTED
- SUPERSEDED
- EXECUTED

A decision state is not equivalent to factual truth.

## 4. Options before selection

Where more than one materially different course exists, the Decision Model MUST preserve considered options and reasons for rejection/selection.

A selected option without auditable rationale is incomplete.

## 5. Evidence binding

Material factual premises in the rationale MUST be traceable to the Case/Evidence layers. Decision rationale MUST NOT invent missing facts to make an option appear preferable.

## 6. Assumptions

Assumptions MUST be explicit and distinguishable from facts. A decision dependent on a material unresolved assumption SHOULD expose the consequence if the assumption fails.

## 7. Risk

Risk evaluation is multi-dimensional and versioned. A single aggregate score MAY be used only if the scoring method is explicit and does not hide component risks.

## 8. Authority

The Decision Model MUST record who/what had authority to make or approve the decision. Automation MUST NOT self-approve decisions requiring independent human/legal authority.

## 9. Abstention

ABSTAIN is valid when:

- evidence is materially insufficient;
- authority is missing;
- problem/constraint is ambiguous;
- required legal/domain rule is unresolved;
- risk cannot be responsibly evaluated.

Abstention SHOULD generate explicit open questions or acquisition actions rather than fabricate certainty.

## 10. Separation from Strategy

Decision chooses or authorizes a direction. Strategy defines how to pursue it. A strategy may change while the underlying decision remains valid.

## 11. Replay

Decision Replay MUST reconstruct at least:

- the Problem version,
- Case Model version,
- EvidenceAssessment versions,
- available options,
- assumptions,
- rationale,
- authority,
- code/evaluator/version identity where automated analysis contributed.

## 12. Failure modes

Decision creation MUST fail closed or remain PROPOSED/ABSTAIN when:

- Problem reference is missing;
- material evidence references are unavailable;
- rationale relies on out-of-scope information;
- required authority is absent;
- rejected alternatives are silently discarded where material;
- assumptions are represented as facts;
- decision cannot be replayed from versioned inputs.

## 13. Validation

KDM-1.0 remains Candidate until:

1. synthetic tests exercise SELECTED, DEFERRED and ABSTAIN;
2. at least one decision compares two viable options;
3. replay reconstructs rationale from exact versioned inputs;
4. Strategy consumes KDM without changing historical decision evidence;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves before CANONICAL.
