# P3 — Measured Result Layer

Status: VALIDATED ON FEATURE HEAD / MERGE GATE PENDING

## Decision need

P2 produced a deterministic `ReasoningRunResult`, but the Product value loop was still open:
reasoning results had no dedicated presentation contract and reasoning behavior had no separate
Gold/KQM measurement path.

P3 closes the technical loop:

`Evidence -> Reasoning -> Structured Result -> Renderer -> Reasoning KQM -> Failure Record`

A failure record is learning-ready evidence. It is not itself a Learning Event and cannot
modify Product state.

## P3.1 — Renderer Contract

`renderer.contract` defines immutable `RenderedResult`, `RendererKind`, and the
`ReasoningRenderer` protocol. Every rendered artifact is bound to the SHA-256 digest of the
source `ReasoningRunResult` and an explicit renderer version.

## P3.2 — JSON Renderer

`JsonReasoningRenderer` emits deterministic canonical JSON from the structured reasoning
result. It does not introduce new reasoning content.

## P3.3 — Markdown Renderer

`MarkdownReasoningRenderer` renders decision, artifacts, evidence references, support links,
rationales, and Open Questions while retaining the source result digest.

## P3.4 — Evidence List Renderer

`EvidenceListRenderer` creates a deterministic evidence-to-artifact map. It allows downstream
reviewers to see which reasoning artifacts depend on each evidence reference.

P3 intentionally does not infer a timeline from support graph order. Support order is not
temporal order. Existing Case timeline renderers remain responsible for real chronology.

## P3.5 — Reasoning Gold Corpus v1 candidate

`data/quality/reasoning_gold_v1.json` is an eight-case synthetic candidate corpus:

- development: 4 cases;
- validation: 2 cases;
- locked evaluation: 2 cases.

The candidate covers structural behaviors including valid evidence-backed conclusion,
unsupported FACT, unresolved support, missing support, multiple evidenced facts, UNKNOWN
support, a locked cycle case, and a locked evidenced-CLAIM case.

The corpus status remains `candidate_pending_independent_review` and `review_status` remains
`not_reviewed`.

## P3.6 — Locked split protection

`ReasoningGoldCorpus.cases_for_split` refuses `locked_evaluation` by default. The public test
suite proves the lock by expecting `LockedReasoningEvaluationError`; it does not execute the
locked cases.

## P3.7 — Reasoning KQM

`evaluate_reasoning_split` measures:

- decision accuracy;
- valid-conclusion recall;
- abstention recall;
- unsafe-conclusion rate;
- Open Question coverage;
- deterministic result digests;
- explicit evaluation failure records.

The evaluator is separate from `ReasoningEngine`; Product code does not import its evaluator.

Verified contract-conformance baseline on feature SHA
`d8406f4c4edc5ec457228a5bead2efa3bacbb826`:

- development 4 cases: accuracy `1.0`, valid-conclusion recall `1.0`, abstention recall `1.0`,
  unsafe-conclusion rate `0.0`, Open Question coverage `1.0`, failures `0`;
- validation 2 cases: the same metric values, failures `0`;
- locked evaluation: **NOT EXECUTED**.

This proves conformance to the small synthetic benchmark contract only. It does not constitute
production/legal reasoning certification.

## P3.8 — Measurement hook

`MeasurementCollector.from_reasoning` converts reasoning KQM metrics into the existing stable
measurement snapshot contract. Measurement observes results but does not promote them.

## P3.9 — SSoT repair

P3 populates previously empty:

- `FOUNDATION.md`;
- `docs/roadmap/LUKART_ROS_MASTER_PLAN.md`.

These documents are derived from actual P0-P2 repository state and the explicit P3 contract.
They do not claim that controlled learning/self-learning is already implemented.

## Non-goals

P3 does not:

- alter reasoning artifacts during rendering;
- infer chronology from support relationships;
- use real/private case material;
- execute extraction or reasoning locked evaluation splits;
- independently review/freeze any Gold Corpus;
- train, tune, or fine-tune models;
- create or promote Learning Events;
- claim production/legal reasoning certification.

## Definition of Done

P3 becomes COMPLETE only when:

1. renderer and reasoning KQM tests pass;
2. full Ruff/MyPy/pytest and repository gates pass;
3. Architectural Audit passes;
4. GitHub App Smoke Test/Stage gate passes on the exact PR head;
5. the exact validated head is merged to `main`;
6. post-merge CI/Audit/Smoke/Stage Orchestrator pass on the merge SHA;
7. final documentation records the measured baseline without overstating certification.
