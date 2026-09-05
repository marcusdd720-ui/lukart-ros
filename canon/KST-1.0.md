# KST-1.0 — Kanon Modelu Strategii

Canonical ID: KST-1.0
Title: Kanon Modelu Strategii
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 3
Owner: Strategy Architecture
Depends On: KMeta-1.0; KMS-1.0; KMP-1.0; KEV-1.0; KDM-1.0
Affects: Planning; Simulation; Renderer; Execution; Case Replay
Supersedes: none
Validation Method: scenario comparison + strategy replay + no-fact-mutation tests
Review Requirement: independent architectural/domain review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KST-1.0 defines Strategy as a versioned model of how to pursue an authorized Decision under known constraints, evidence state and risk. Strategy answers `How may we pursue the selected direction?`.

## 2. Definition

`StrategyModel = <strategy_id, decision_ref, objectives, approach_options, selected_approach, sequencing_constraints, dependencies, risk_controls, evidence_actions, communication_actions, execution_preconditions, fallback_paths, status, version, lineage>`

## 3. Strategy is downstream of Decision

Strategy MUST reference an explicit Decision Model. It MUST NOT invent a new decision need or silently replace the selected decision.

If analysis reveals the decision is no longer valid, Strategy MUST request decision reconsideration rather than mutate the decision record.

## 4. Objectives

Strategy objectives derive from the authorized decision and Problem success criteria. They may be ordered by priority but MUST preserve trade-offs and constraints.

## 5. Approaches

Materially different approaches SHOULD be represented before selection when alternatives exist, e.g. collect evidence first, negotiate, file, defend, monitor, abstain/seek human review.

## 6. Evidence actions

Strategy may request collection or validation of missing evidence but MUST NOT mark anticipated evidence as already existing.

## 7. Risk controls

Risk controls may include thresholds, stop conditions, human approval points, privacy constraints and fallback triggers.

## 8. Simulation boundary

Simulations/what-if analyses are derived artifacts. They MAY compare strategies but MUST keep assumptions explicit and MUST NOT write simulated outcomes into Case facts.

## 9. Separation from Plan

Strategy expresses approach and sequencing logic. Plan translates strategy into concrete executable tasks with owners, deadlines/preconditions and completion criteria.

## 10. Separation from Document

Strategy does not generate prose. Communication/document generation is downstream and consumes an approved Strategy/Plan plus factual/evidence bindings.

## 11. Failure modes

Strategy MUST remain PROPOSED/ABSTAIN when:

- no valid Decision reference exists;
- required evidence/authority precondition is missing;
- approach requires out-of-scope data or unauthorized action;
- simulated outcome is treated as fact;
- strategy silently changes Case facts or Decision rationale;
- fallback/stop conditions required by risk policy are absent.

## 12. Validation

KST-1.0 remains Candidate until:

1. synthetic tests compare at least two strategy approaches for one Decision;
2. missing-evidence strategy actions do not promote evidence state;
3. simulation artifacts remain separated from Case facts;
4. Plan consumes Strategy without changing it;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves before CANONICAL.
