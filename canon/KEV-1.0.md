# KEV-1.0 — Kanon Domeny Dowodowej

Canonical ID: KEV-1.0
Title: Kanon Domeny Dowodowej
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Evidence Architecture
Depends On: KMeta-1.0; CK-1.0; KMR-1.0; TM-1.0; KCS-1.2; KMS-1.0; KMP-1.0
Affects: Reasoning; Decision; Strategy; Validation; Renderer; Case Replay
Supersedes: none
Validation Method: synthetic evidence matrices + contradiction/missing-evidence tests + current provenance mapping
Review Requirement: independent architectural/domain review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KEV-1.0 defines the Evidence domain as a separate analytical layer responsible for evaluating whether available material can support, contradict, or fail to establish propositions required by a Problem Model.

Evidence is not the same thing as Reasoning. Evidence answers `what support exists and how usable is it?`; Reasoning answers `what follows from the supported model under explicit rules?`.

## 2. Evidence assessment object

`EvidenceAssessment = <assessment_id, problem_ref, proposition_ref, support_refs, contradiction_refs, provenance_state, authenticity_state, relevance_state, completeness_state, strength_state, burden_ref, missing_evidence, limitations, evaluator_version, created_at>`

Assessment fields are derived analytical outputs. They MUST NOT overwrite object-level epistemic state in KMR.

## 3. Core dimensions

The Evidence domain SHOULD assess at least:

- provenance,
- authenticity/integrity where assessable,
- relevance,
- completeness,
- consistency,
- strength/weight,
- contradiction,
- missing evidence,
- burden/threshold where defined by the Problem/domain contract,
- traceability.

## 4. Provenance before strength

Evidence strength MUST NOT be assigned without first establishing what source/object is being assessed and how it is linked to the proposition.

A model-generated statement cannot serve as primary source evidence merely because it appears coherent.

## 5. Completeness

Completeness is relative to a defined proposition/problem requirement, not an abstract percentage of all possible knowledge.

The domain MUST be able to express:

- complete for current decision need,
- incomplete but non-blocking,
- materially incomplete,
- unknown completeness.

## 6. Contradictions

Contradictory evidence is preserved. The Evidence domain may compare provenance/quality, but MUST NOT silently delete the weaker side.

Resolution requires a documented assessment rule or new evidence and remains auditable.

## 7. Missing evidence

A missing-evidence object SHOULD identify:

- proposition/element affected,
- why current material is insufficient,
- candidate evidence/source type,
- whether the gap blocks decision,
- acquisition feasibility if known.

## 8. Burden and threshold

Burden/threshold is external to raw evidence and comes from Problem/domain/legal rules. KEV may evaluate evidence against the referenced burden but MUST preserve the authority/provenance of the burden rule.

## 9. Separation from KMR/KMS

KMR/KMS hold representations and references. KEV computes assessments over them.

An EvidenceAssessment MUST be versioned and evaluator-bound so later methodology changes do not rewrite historical assessments.

## 10. Separation from Decision

Evidence sufficiency does not itself choose strategy. A Decision layer may accept risk, seek more evidence, settle, abstain, or choose another path.

## 11. Failure modes

Evidence assessment MUST fail closed or remain UNKNOWN when:

- proposition being assessed is undefined;
- source/provenance identity is missing where required;
- evidence is out of Case scope/authorization;
- burden rule is asserted without source/contract;
- strength score has no declared evaluator/method;
- contradictory material is silently omitted;
- completeness is claimed without a defined evidence need.

## 12. Validation

KEV-1.0 remains Candidate until:

1. current provenance/evidence graph implementation is mapped to this contract;
2. synthetic tests cover strong support, contradiction, missing evidence and unknown provenance;
3. one Problem Model produces multiple proposition-level assessments;
4. Decision layer consumes assessments without mutating underlying Case facts;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves before CANONICAL.
