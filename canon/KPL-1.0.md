# KPL-1.0 — Kanon Planu Działań

Canonical ID: KPL-1.0
Title: Kanon Planu Działań
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 3
Owner: Planning Architecture
Depends On: KMeta-1.0; KMP-1.0; KDM-1.0; KST-1.0
Affects: Execution; Communication; Renderer; Monitoring; Case Replay
Supersedes: none
Validation Method: executable-plan tests + dependency/order tests + replay
Review Requirement: independent architectural/domain review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

KPL-1.0 defines the Plan as a concrete, versioned translation of an approved Strategy into executable actions. Plan answers `What do we do now, in what order, under which preconditions, and how do we know an action is complete?`.

## 2. Definition

`ActionPlan = <plan_id, strategy_ref, tasks, dependencies, owners, preconditions, deadlines, completion_criteria, approval_points, monitoring_hooks, fallback_triggers, status, version, lineage>`

## 3. Task contract

Each material task SHOULD define:

- task identity,
- purpose,
- required inputs,
- authorized actor/owner,
- preconditions,
- expected output artifact/action,
- completion criteria,
- failure mode,
- escalation/approval rule,
- dependency identities.

## 4. Ordering and dependencies

Plan order MUST be derived from explicit dependencies and constraints. Tasks MUST NOT execute merely because they are listed earlier in prose.

## 5. Deadlines

Deadlines consume TM temporal semantics plus authoritative domain/legal rules. A deadline engine MUST preserve the rule/source used to calculate a date.

## 6. Approval points

Where policy requires human or external approval, the task remains BLOCKED/PENDING until that approval exists. Automation MUST NOT infer approval from absence of objection.

## 7. Completion

Task completion MUST be evidence-based: produced artifact, recorded external event, validated state transition or explicit authorized closure.

## 8. Plan changes

A material plan change creates a new Plan version. Historical task states remain reconstructable.

If the underlying Strategy or Decision becomes invalid, Plan MUST suspend affected tasks and request upstream reconsideration.

## 9. Separation from Execution

Plan specifies authorized work; Execution performs it. Existence of a task does not grant an agent authority beyond its execution contract.

## 10. Separation from Document

A document may be one task output. Plan defines why/when it is needed and required content bindings; the document renderer defines presentation.

## 11. Failure modes

Plan execution MUST fail closed or remain blocked when:

- Strategy reference is invalid/superseded;
- required approval is missing;
- task authority is insufficient;
- deadline provenance/rule is unknown where material;
- dependencies are cyclic or unresolved;
- completion is claimed without evidence;
- task attempts to mutate upstream Case/Decision state outside normal Update contracts.

## 12. Validation

KPL-1.0 remains Candidate until:

1. synthetic plans cover dependencies, blocked approval and fallback;
2. one plan includes evidence acquisition and document production as separate tasks;
3. deadline calculation preserves source/rule identity;
4. Case Replay reconstructs task progression;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves before CANONICAL.
