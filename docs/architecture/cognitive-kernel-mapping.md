# Cognitive Architecture — implementation mapping

Status: implementation evidence for Candidate Canon documents
Canonical baseline: `f4f065a71a7e01b53dd9a8eb9c749ab116784dbf`

This document maps existing Product/Factory components to the Candidate cognitive contracts introduced in PR #68. A mapping is evidence of existing implementation coverage; it does not promote any Candidate Canon to CANONICAL.

## 1. CK-1.0 — Cognitive Kernel boundary

| CK responsibility | Existing implementation | Coverage | Gap / next action |
| --- | --- | --- | --- |
| epistemic state vocabulary | `knowledge/epistemic.py::KnowledgeStatus` | IMPLEMENTED | keep vocabulary aligned with FOUNDATION |
| controlled epistemic transitions | `knowledge/epistemic.py::EpistemicStatusMachine` | IMPLEMENTED | expand transition evidence semantics only through separate contract/change |
| fail-closed promotion to FACT | `EpistemicStatusMachine.decide/require` | IMPLEMENTED | retain negative regression tests |
| evidence/provenance references | knowledge graph/evidence artifacts + reasoning support lineage | PARTIAL | normalize representation under KMR rather than duplicate schemas |
| immutable replay identity | `knowledge/case_replay.py::CaseReplayRecord` | IMPLEMENTED | extend future replay identity for cognitive-model schema versions |
| model Build / Update / Query separation | distributed across builder/graph/runtime | PARTIAL | introduce explicit contracts before refactoring implementation |
| explicit unknown/open questions | `reasoning/open_questions.py` + epistemic UNKNOWN/UNRESOLVED | IMPLEMENTED/PARTIAL | map open-question schema to KMR/KMP |
| contradiction preservation | `knowledge/contradiction_detector.py` + reasoning validation | PARTIAL | preserve contradiction assessment as derived/versioned artifact |
| validation hooks without implicit trust mutation | validation/KQM/Factory architecture | IMPLEMENTED | retain Factory != Product boundary |
| privacy-bounded query scope | local private case storage exists | PARTIAL | KCS ScopePolicy/ReferenceSet are not yet runtime contracts |

## 2. KMR-1.0 — Cognitive representation

### Existing coverage

- `knowledge/epistemic.py` supplies the canonical epistemic vocabulary and controlled transition machine.
- Knowledge Graph nodes/edges provide identity and typed graph relations.
- Provenance/evidence references exist in extraction, reasoning and validation paths.
- `CaseReplayRecord` already binds graph SHA-256, source SHA-256, manifest, pipeline, agent contracts and renderer identity.

### Missing contract coverage

The current Product does not yet expose one normalized `CognitiveObject` contract containing all KMR fields:

- stable logical identity;
- typed payload;
- epistemic state;
- provenance references;
- valid/event time;
- knowledge time;
- immutable version;
- lineage/change-set identity.

Do not migrate existing graph data until an adapter/compatibility path is tested.

## 3. TM-1.0 — Temporal model

### Existing coverage

- Case snapshots have a system timestamp.
- Case/domain facts and timeline artifacts can carry event dates.
- source documents preserve source metadata where extraction supports it.

### Gap

Current runtime does not consistently distinguish the four TM axes:

1. event time;
2. source/document time;
3. knowledge time;
4. system/version time.

`knowledge/models/case_snapshot.py` currently uses a single snapshot timestamp for the run. This is valid as system time but must not be reused as event/source/knowledge time.

## 4. KCS-1.2 — Case boundary

### Existing coverage

`core/case_manager.py` creates private local Case workspaces under the configured local data root and writes basic case metadata. `core/local_case_store.py` and `validation/local_private_pilot.py` enforce the private-data boundary.

### Gap

Current `case.yaml` does not yet model:

- `ScopePolicy`;
- `ReferenceSet`;
- accountable ownership/authority;
- separate operational and epistemic states;
- versioned goals/decision needs.

This is the first recommended Product vertical slice after the Canon validation infrastructure is stable.

## 5. KMS-1.0 — Case Model

### Existing coverage

- Knowledge Graph represents Case-related objects and relations.
- Case snapshots provide immutable run-level state summaries.
- timelines, evidence artifacts and reports are tied to a Case workspace.

### Gap

There is no explicit immutable `CaseModel` projection contract separating:

`global/available knowledge -> authorized Case projection -> Problem-specific analysis`.

Introduce an adapter first; do not replace the graph.

## 6. KMP-1.0 — Problem Model

### Existing coverage

Reasoning currently consumes tasks/issues and can produce decisions/open questions, but there is no canonical Problem Model separating the decision need from the Case Model.

### Gap

Need a typed Problem contract with:

- decision need;
- desired outcomes;
- constraints;
- evidence needs;
- open questions;
- risk dimensions;
- success criteria.

One Case must be able to support multiple Problem Models without changing Case facts.

## 7. KEV-1.0 — Evidence domain

### Existing coverage

- provenance;
- evidence-readiness logic;
- contradiction detection;
- extraction quality;
- E2E/adversarial evidence gates;
- renderer evidence coverage checks.

### Gap

Evidence dimensions are currently distributed. Need a typed `EvidenceAssessment` adapter that keeps provenance/authenticity/relevance/completeness/strength/missing-evidence/burden separate from raw Case facts and from Reasoning conclusions.

## 8. KDM-1.0 — Decision Model

### Existing coverage

Reasoning models produce typed decisions and support abstention/open questions.

### Gap

Need a durable decision artifact preserving:

- options considered;
- assumptions;
- evidence-assessment refs;
- rejected options;
- selected option;
- rationale;
- authority;
- version/replay lineage.

## 9. KST-1.0 — Strategy Model

### Existing coverage

Step 13 Strategy Benchmark / capability routing provides measured routing/strategy infrastructure.

### Gap

Routing is not the same as a Case-level legal/problem strategy artifact. Need explicit Strategy Model downstream of KDM and upstream of Plan.

## 10. KPL-1.0 — Action Plan

### Existing coverage

Factory has strong staged workflow orchestration, but Product Case actions do not yet share a canonical Plan contract.

### Gap

Need Product task semantics with preconditions, authority, dependencies, deadline provenance, completion evidence and approval points.

## 11. KCB-1.0 — Case Bridge

### Existing coverage

Private Case isolation exists.

### Gap

There is intentionally no direct Case-to-Case transfer mechanism yet. Before implementation, create adversarial tests proving:

- no direct enumeration of another Case;
- candidate discovery does not leak protected content;
- approved import goes through target `ReferenceSet`;
- revocation preserves audit history and triggers propagation review.

## 12. KDOC-1.0 — Document/Renderer boundary

### Existing coverage

`FOUNDATION.md` already states Renderer may present reasoning state but cannot rewrite it. Existing renderer-quality tests cover source binding, evidence coverage, epistemic status, open questions and lossy rendering. Production Validation Step 16 intentionally remains blocked pending independent human review.

### Gap

Future legal/document generation should consume explicit Case/Problem/Evidence/Decision/Strategy/Plan artifacts. Do not move legal analysis into the renderer.

## 13. Implementation order

The smallest safe runtime path is:

1. Canon metadata/dependency validator.
2. KCS runtime contract (`ScopePolicy`, `ReferenceSet`, separate states) as backward-compatible adapter.
3. KMS immutable projection contract.
4. KMP Problem Model.
5. KEV EvidenceAssessment adapter.
6. KDM Decision artifact.
7. KST Strategy artifact.
8. KPL Plan artifact.
9. KDOC input binding to those artifacts.
10. KCB only after isolation/adversarial tests exist.

Each step must use fresh-SHA validation and Case Replay where the change affects Product semantics.
