# P2 — Controlled Reasoning Core

Status: IMPLEMENTED pending validation

## Decision need

LUKART ROS needs a Product-layer reasoning core that can distinguish evidence-backed conclusions from unsupported or unresolved reasoning. Engineering PASS alone must not be represented as analytical correctness.

## Scope

P2 adds a deterministic reasoning kernel on top of the existing epistemic status machine.

### P2.1 — Reasoning Artifact Model

`ReasoningArtifact` is a typed, immutable statement containing:

- stable `artifact_id`,
- explicit `KnowledgeStatus`,
- statement text,
- evidence references,
- support artifact references,
- rationale,
- deterministic canonical digest.

### P2.2 — Evidence Support Graph

`validate_reasoning_graph` enforces fail-closed invariants:

- `FACT` requires explicit evidence references,
- `CONCLUSION` and `RECOMMENDATION` require support artifacts,
- referenced support artifacts must exist,
- support cycles are invalid,
- derived results require an evidence-backed lineage,
- unresolved/rejected-only support cannot justify a derived result.

### P2.3 — Open Questions Ledger

Validation gaps are converted into deterministic `OpenQuestion` artifacts. Unknown or unresolved information remains visible rather than being silently filled by a model.

### P2.4 — Minimal Reasoning Engine

`ReasoningEngine` evaluates an explicit conclusion artifact. It does not generate missing facts or conclusions. It traverses the support lineage and validates the relevant reasoning graph.

### P2.5 — Calibrated Abstention

The engine returns `ABSTAIN` when:

- the requested conclusion does not exist,
- the requested artifact is not a `CONCLUSION`,
- support is missing or invalid,
- a support cycle exists in the relevant lineage,
- the lineage contains `UNKNOWN`, `UNRESOLVED`, or `REJECTED` knowledge.

Abstention includes explicit open questions.

### P2.6 — Epistemic Transition Binding

`transition_artifact` delegates status changes to the canonical `EpistemicStatusMachine`. Reasoning artifacts therefore cannot bypass the P1 rule that promotion to `FACT` requires new Evidence.

### P2.7 — Structured Reasoning Result

`ReasoningRunResult` is renderer-ready and deterministic. It keeps artifacts, open questions and the final `CONCLUDE`/`ABSTAIN` decision separate from presentation prose and exposes a canonical SHA-256 digest.

## Non-goals

P2 does not:

- claim that a model-generated sentence is evidence,
- automatically resolve contradictions,
- tune or fine-tune an LLM,
- execute or modify locked evaluation data,
- implement a presentation renderer,
- promote learning candidates into trusted knowledge,
- replace KQM/Gold Corpus analytical evaluation.

## Product / Factory boundary

`reasoning/` is Product runtime code. It is included in package discovery and in the runtime dependency-boundary gate so imports from `factory` fail CI.

## Definition of Done

P2 is COMPLETE only when:

1. all P2 contracts and tests exist,
2. focused and repository-wide engineering gates pass,
3. Architectural Audit passes,
4. GitHub App Smoke Test and Stage 16 pass,
5. the exact validated PR head is merged to `main`,
6. post-merge CI/Audit/Smoke/Stage Orchestrator pass on the merge SHA.

P2 engineering completion does not equal analytical certification. KQM/Gold Corpus remains a separate requirement for measured analytical quality.
