# KMR-1.0 — Kanon Modelu Reprezentacji Poznawczej

Canonical ID: KMR-1.0
Title: Kanon Modelu Reprezentacji Poznawczej
Version: 1.0
Status: CANDIDATE CANON
Class: EPISTEMOLOGY
Stability Index: 4
Owner: Core Architecture
Depends On: KMeta-1.0; CK-1.0; FOUNDATION.md
Affects: Knowledge Graph; Epistemic Status Machine; Model Świata; KCS; KMS; KMP; Evidence
Supersedes: none
Validation Method: schema mapping + transition tests + replay validation + independent review
Review Requirement: independent architectural/epistemic review before CANONICAL
Change Policy: versioned schema/semantic change only

## 1. Purpose

KMR-1.0 defines the smallest canonical cognitive representation used by Artur OS. It separates the identity and content of a cognitive object from analytical metrics computed about the model.

## 2. Core principle

Every material entity and every material relation represented in the cognitive model carries its own epistemic state and provenance. Hypotheses are not a separate storage layer; they are objects/relations whose epistemic state expresses hypothesis status.

## 3. Cognitive Object

A Cognitive Object is the tuple:

`CO = <id, type, payload, epistemic_state, provenance_refs, valid_time, knowledge_time, version, lineage>`

Minimum semantics:

- `id` — stable logical identity;
- `type` — explicit object type;
- `payload` — typed domain content;
- `epistemic_state` — current epistemic classification;
- `provenance_refs` — references to supporting/contradicting source material;
- `valid_time` — when the represented proposition/event is asserted to be true in the domain, if applicable;
- `knowledge_time` — when the system learned/recorded the representation;
- `version` — immutable version identity;
- `lineage` — predecessor/change-set identity needed for audit/replay.

## 4. Relation

A Relation is not epistemically privileged over an Entity.

A relation whose truth matters to reasoning MUST be represented with its own:

- stable identity,
- relation type,
- endpoints,
- epistemic state,
- provenance,
- version/lineage.

The existence of two entities does not imply a relation between them.

## 5. Epistemic states

KMR adopts the repository canonical vocabulary currently defined in FOUNDATION:

- FACT
- CLAIM
- INTERPRETATION
- HYPOTHESIS
- CONCLUSION
- RECOMMENDATION
- UNKNOWN
- UNRESOLVED
- REJECTED

KMR does not redefine promotion rules owned by the Epistemic Status Machine. It requires every transition to be explicit, auditable and evidence-bound where the transition contract requires evidence.

## 6. Metrics are not model facts

The following are derived analytical outputs and MUST NOT be stored as intrinsic truth fields of a Cognitive Object unless represented explicitly as a versioned assessment object with provenance to the evaluator:

- global consistency score,
- confidence score derived by TIMR,
- evidence completeness score,
- conflict count,
- risk score,
- aggregate uncertainty metric.

TIMR/evaluators may compute them from a model snapshot. Their result is an assessment artifact, not source evidence.

## 7. Provenance

A provenance reference SHOULD include, where available:

- source/document identifier,
- source location/span/page/section,
- content hash,
- extractor/processor identity and version,
- timestamp/knowledge-time,
- integrity identity of source artifact.

A generated statement does not become provenance merely because it appears in a prior model output.

## 8. Time semantics

KMR distinguishes at minimum:

- `valid_time` — domain/event validity time;
- `knowledge_time` — time at which Artur OS obtained/recorded the knowledge.

Document/source creation or publication time is source metadata and may differ from both. Full temporal semantics are delegated to TM-1.0.

## 9. Versioning

A semantic update MUST create a new object version or explicit Change Set. Historical versions remain reconstructable.

Forbidden behavior:

- silently mutating an old FACT because later evidence changed the conclusion;
- deleting a rejected hypothesis so that the historical reasoning trail disappears;
- rewriting provenance to point to stronger evidence discovered later without recording the update.

## 10. Build and Update

Build may create initial Cognitive Objects from a bounded source set.

Update may:

- add an object/relation,
- add provenance,
- change epistemic state under the canonical transition contract,
- reject/deprecate a prior proposition while preserving history,
- create new relations,
- split or merge logical identities only through an auditable identity-resolution operation.

## 11. Unknowns and contradictions

UNKNOWN and UNRESOLVED are valid model states.

Contradiction is represented through explicit typed relations/assessment artifacts and preserved until resolved by a documented rule or new evidence. KMR does not permit resolution by model preference alone.

## 12. Identity rules

Identity resolution MUST be explicit. Similar labels, names or values do not prove identity.

Where identity cannot be safely resolved, distinct objects remain distinct and an unresolved candidate-equivalence relation may be created.

## 13. Failure modes

Creation/update MUST fail closed or remain unresolved when:

- required type/schema is absent;
- source/provenance required by the contract is missing;
- requested epistemic promotion is unauthorized;
- identity merge is ambiguous;
- history would become non-reconstructable;
- derived metric is being promoted as source evidence;
- relation endpoints cannot be resolved without guessing.

## 14. Validation

KMR-1.0 remains Candidate until:

1. current Knowledge Graph / epistemic implementation is mapped to KMR fields;
2. transition tests prove prohibited promotions fail closed;
3. Case Replay proves historical object versions/provenance can be reconstructed for a synthetic case;
4. TM-1.0 resolves temporal field semantics without conflict;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent review approves the representation contract before CANONICAL.
