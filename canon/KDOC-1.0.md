# KDOC-1.0 — Kanon Dokumentu i Renderera

Canonical ID: KDOC-1.0
Title: Kanon Dokumentu i Renderera
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 3
Owner: Communication Architecture
Depends On: KMeta-1.0; KMS-1.0; KMP-1.0; KEV-1.0; KDM-1.0; KST-1.0; KPL-1.0; FOUNDATION.md
Affects: Renderer; Dossier; Document Generator; Client Communication; Audit
Supersedes: none
Validation Method: source-binding tests + lossy-renderer tests + human dossier review
Review Requirement: independent human/architectural review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KDOC-1.0 defines the document/renderer layer as a presentation and communication layer. It must not become an alternate reasoning or legal-analysis authority.

## 2. Dumb renderer principle

A renderer/document generator receives already-authorized structured inputs and transforms them into a presentation artifact. It MUST NOT independently promote facts, invent legal conclusions, resolve contradictions, select strategy, or change decision rationale.

## 3. Inputs

A final document MAY consume only explicit structured references such as:

- Case Model version,
- Problem Model version,
- EvidenceAssessment versions,
- Decision Model version,
- Strategy Model version,
- Action Plan version,
- approved authorities/templates,
- communication target/context.

## 4. Output binding

Every material document SHOULD be bound to:

- renderer/template identity and version,
- input artifact identities/versions,
- exact source/result digest,
- generation timestamp,
- human approval if required.

## 5. No hidden analysis

If generation requires a new factual inference, legal interpretation, evidence assessment or strategy choice, generation MUST stop and request the appropriate upstream artifact instead of making the decision locally.

## 6. Traceability

Material factual/legal assertions in professional outputs SHOULD be traceable to structured upstream artifacts and, where applicable, underlying provenance/authority.

## 7. Losslessness

Presentation MAY summarize, but MUST NOT silently omit material unresolved questions, abstentions, contradictory evidence, limitations or decision conditions when those elements are required by the output contract.

## 8. Templates

Templates define structure/style, not truth. A template may request required sections or fields but may not manufacture missing content.

## 9. Human review

Where a filing, legal position, privileged communication or other high-risk output requires human review, the artifact remains DRAFT/REVIEW_REQUIRED until that review is recorded.

## 10. Separation from execution

Creation of a final document does not itself authorize sending, filing or publication. Those actions require Plan/Execution authority.

## 11. Failure modes

Rendering MUST fail closed or produce explicit placeholders/review requirements when:

- upstream artifact is missing/superseded;
- source binding cannot be established;
- template requires data not supported by upstream model;
- renderer would need to choose between contradictory facts;
- required human approval is absent;
- output would conceal material unresolved state.

## 12. Validation

KDOC-1.0 remains Candidate until:

1. current JSON/Markdown renderer is mapped to this contract;
2. existing lossy-renderer tests remain PASS;
3. representative dossier preserves evidence/epistemic/open-question visibility;
4. Step 16 independent human renderer review is completed for the existing production-validation track;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves before CANONICAL.
