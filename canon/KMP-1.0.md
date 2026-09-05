# KMP-1.0 — Kanon Modelu Problemu

Canonical ID: KMP-1.0
Title: Kanon Modelu Problemu
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Problem Architecture
Depends On: KMeta-1.0; CK-1.0; KMR-1.0; TM-1.0; KCS-1.2; KMS-1.0
Affects: Evidence; Reasoning; Decision; Strategy; Planning; Renderer
Supersedes: none
Validation Method: synthetic multi-problem cases + decision-need tests + scope/relevance tests
Review Requirement: independent architectural/domain review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KMP-1.0 defines a Problem Model as the explicit decision/question structure that Artur OS is attempting to resolve inside a Case. It answers: `What problem are we solving, for whom, under which constraints, and what would count as an adequate resolution?`

## 2. Definition

`ProblemModel = <problem_id, case_model_ref, decision_need, stakeholder_interests, desired_outcomes, constraints, legal_or_domain_frames, evidence_needs, open_questions, risk_dimensions, success_criteria, status, version, lineage>`

## 3. Decision Need First

Every active Problem Model MUST contain an explicit `decision_need` before strategy generation.

Document generation instructions such as `write an appeal` are not sufficient unless linked to the underlying decision/problem being addressed.

## 4. Multiple problems per Case

A single Case may contain multiple Problem Models. Example classes include:

- liability/existence of obligation,
- limitation/prescription,
- procedural admissibility,
- evidence sufficiency,
- damages/compensation,
- enforcement/collection,
- settlement/negotiation.

Problems MUST NOT be silently merged when they require different facts, evidence or legal tests.

## 5. Stakeholders and interests

KMP distinguishes:

- factual actors from KMS,
- represented stakeholder/client interests,
- opposing/third-party interests where relevant,
- system/legal constraints.

An inferred interest MUST retain inferential epistemic status and MUST NOT be treated as a directly observed fact.

## 6. Desired outcomes

Desired outcome states describe what the stakeholder wants. They are not predictions and not legal conclusions.

KMP SHOULD distinguish:

- ideal outcome,
- acceptable outcome,
- minimum protective outcome,
- prohibited/unacceptable outcome.

## 7. Constraints

Constraints may include:

- jurisdiction/procedure,
- deadlines,
- burden of proof,
- available authority,
- privacy/confidentiality,
- cost/resource constraints,
- client instructions,
- non-negotiable safety/compliance rules.

A constraint MUST be provenance-bound when it derives from external law/source material.

## 8. Evidence needs

Problem Model defines what must be established, disproved or clarified. It does not itself score evidence.

Evidence needs SHOULD identify:

- proposition/element to establish,
- burden/threshold if known,
- current supporting references,
- missing evidence categories,
- blocking contradictions,
- status of sufficiency assessment.

Evidence scoring belongs downstream to Evidence domain.

## 9. Open questions

Open questions are first-class problem elements. A Problem Model may remain valid while unresolved; the downstream Decision/Strategy layer must decide whether uncertainty is tolerable or requires abstention/additional collection.

## 10. Risk dimensions

Risk is represented as dimensions/candidates rather than one opaque score. Examples:

- legal merits,
- evidentiary,
- procedural,
- timing,
- financial,
- reputational,
- privacy/compliance,
- execution/enforcement.

Metric/scoring policy belongs to downstream evaluators.

## 11. Success criteria

Success criteria define conditions for considering the problem operationally resolved. They MAY include accepted residual uncertainty.

Problem closure MUST NOT require perfect knowledge.

## 12. Separation from Case Model

KMP may query KMS but MUST NOT mutate Case facts to fit a preferred problem framing.

If new facts are required, they must enter through the normal Case/Model Update path.

## 13. Separation from Decision and Strategy

KMP does not choose between available courses of action. It defines the problem space against which options are later evaluated.

A change of strategy does not require changing KMP unless the underlying decision need, constraints or desired outcomes change.

## 14. Failure modes

Problem construction MUST fail closed, remain PROPOSED or create open questions when:

- decision need is absent/ambiguous;
- problem scope exceeds authorized Case scope;
- legal/domain frame is asserted without authority/provenance where required;
- desired outcome is presented as predicted fact;
- multiple materially different problems are silently collapsed;
- strategy recommendation is embedded as if it were a problem fact.

## 15. Validation

KMP-1.0 remains Candidate until:

1. one synthetic Case demonstrates at least two distinct Problem Models over the same KMS;
2. evidence needs differ appropriately by Problem without changing Case facts;
3. ambiguous decision need produces an explicit open question/abstention rather than strategy;
4. Strategy/Decision contracts consume KMP as immutable input;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves before CANONICAL.
