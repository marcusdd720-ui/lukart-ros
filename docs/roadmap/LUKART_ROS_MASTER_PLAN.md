# LUKART ROS / KOS — Master Plan

Status: Active dependency-driven roadmap

## Roadmap rule

Programs advance by dependency and measured need, not by feature attractiveness. A later
program may be researched early, but production implementation must not bypass required
contracts, validation, Gold/KQM measurement, privacy boundaries, or promotion gates.

Status vocabulary follows `AGENTS.md`: PLANNED, IN_PROGRESS, IMPLEMENTED, VALIDATED,
CERTIFIED, COMPLETE, BLOCKED.

## P0 — Controlled Agent Foundation

Status: **COMPLETE**

Delivered:

1. `AGENTS.md v2` enterprise operating contract.
2. controlled GitHub write policy/workflow.
3. Agent Step Contract.
4. Agent Registry.
5. Agent Runner and Validation Gate.
6. deterministic ReferenceFactAgent vertical slice.
7. Agent Evaluation and Certification decision model.
8. extraction Gold/KQM technical vertical slice.

Measured result: ReferenceFactAgent is technically valid but analytically REJECTED under the
current experimental extraction thresholds. Extraction locked evaluation remains untouched.

## P1 — Controlled Multi-Agent Runtime

Status: **COMPLETE**

Delivered:

1. typed multi-agent workflow orchestration;
2. canonical Epistemic Status Machine;
3. ContradictionAgent adapter;
4. review-only ReviewerAgent;
5. Agent Competency Profiles;
6. fail-closed Capability Router;
7. deterministic Case Replay envelope.

Core result: capability, execution, review, epistemic authority, and certification are now
separate concepts enforced by contracts.

## P2 — Controlled Reasoning Core

Status: **COMPLETE**

Delivered:

1. immutable ReasoningArtifact model;
2. evidence-backed support graph validation;
3. Open Questions Ledger;
4. deterministic ReasoningEngine;
5. calibrated `ABSTAIN` behavior;
6. binding to the canonical Epistemic Status Machine;
7. deterministic renderer-ready `ReasoningRunResult` with digest.

Core result: LUKART can distinguish a structurally supported conclusion from reasoning that
must abstain because evidence/support is missing, cyclic, unknown, unresolved, or rejected.

P2 engineering completion does not by itself certify real-world reasoning quality.

## P3 — Measured Result Layer

Status: **COMPLETE**

Delivered:

1. Reasoning Renderer Contract.
2. deterministic JSON renderer.
3. deterministic Markdown renderer.
4. deterministic evidence-list renderer.
5. protected synthetic Reasoning Gold Corpus v1 candidate.
6. Reasoning KQM evaluator and failure records.
7. generic measurement hook for reasoning metrics.
8. populated `FOUNDATION.md` and this roadmap from verified repository state.
9. feature and post-merge CI/Audit/Smoke/Stage validation.

Verified contract-conformance baseline:

- development 4 cases: decision accuracy `1.0`, valid-conclusion recall `1.0`, abstention
  recall `1.0`, unsafe-conclusion rate `0.0`, Open Question coverage `1.0`, failures `0`;
- validation 2 cases: the same metric values, failures `0`;
- locked evaluation: **NOT EXECUTED**.

P3 does not claim production reasoning certification. The reasoning corpus remains a candidate
until independent review/freeze requirements are satisfied, and its locked split remains
unexecuted during development/validation.

## P4 — Controlled Learning Foundation

Status: **COMPLETE**

Delivered:

1. immutable Measured Failure contract with evaluator/result/report/SHA provenance;
2. Failure Corpus generated only from measured, traceable evaluator failures;
3. Learning Candidate / hypothesis representation separated from trusted knowledge;
4. bounded Experiment Contract with sandbox, split, revision, metric, and run-budget binding;
5. fail-closed Promotion Gate based on measured deltas and metric guardrails;
6. explicit `ELIGIBLE_FOR_PROMOTION`, `REJECTED`, and `INCONCLUSIVE` decision states;
7. locked evaluation prohibited as learning/tuning input;
8. runtime dependency boundary extended to `learning/`;
9. adversarial tests for provenance, locked data, revision binding, non-finite metrics,
   malformed digests, guardrail regression, contract mismatch, and run-budget violations;
10. Reasoning KQM evaluator provenance separated from Reasoning Engine provenance.

Target loop:

`Measured Failure -> Failure Corpus -> Learning Candidate -> Experiment -> KQM Delta -> Promotion Decision`

A promotion decision is an immutable eligibility artifact only. P4 intentionally provides no
API for directly mutating canonical knowledge, prompts, rules, routing, code, models, agent
certification, or production release state.

Final feature head `6727cd34be12f80a29499b70f7641eef7a42f0bc` passed CI Foundation on
Python 3.11/3.12/3.13, Architectural Audit 1.0, GitHub App Smoke Test, and its dispatched Stage
Gate, and was merged without further branch changes.

Implementation merge `082358d28a336fa648e5cc05bb2a9d7a656c64af` then passed post-merge:

- CI Foundation on Python 3.11, 3.12, and 3.13;
- Architectural Audit 1.0;
- Stage Orchestrator;
- GitHub App Smoke Test;
- smoke-dispatched Stage Gate.

Core result: measured failures can now become traceable improvement hypotheses and bounded
experiments, while promotion remains a measured eligibility decision rather than authority to
self-modify production state.

P4 engineering completion does not certify the reasoning Gold candidate as production truth and
does not authorize locked evaluation for tuning.

## P5 — Agent Teaching and Distillation

Status: **VALIDATED IMPLEMENTATION / FINAL MERGE GATE PENDING** on
`feat/agent-teaching-p5`.

Implemented scope:

1. immutable Gold and measured-Failure Teaching Example manifests;
2. digest-bound source, input, expected-output, and evidence provenance;
3. teaching input restricted to `development` and `validation` splits;
4. locked evaluation, production, and arbitrary test splits rejected fail-closed;
5. independent Teaching Approval for every exact example digest;
6. automated/system/factory reviewer identities prohibited;
7. P4 Learning Candidate + Experiment Contract + eligible Promotion Decision binding;
8. P5 distillation limited to prompt/retrieval/rule/model changes;
9. deterministic semver Agent Teaching Package bound to exact Agent Contract SHA-256;
10. mandatory exact-contract recertification before agent release eligibility;
11. adversarial tests for locked data, approval failure, provenance mismatch, unsupported
    change kinds, immutable artifacts, and recertification mismatch.

Target loop:

`Approved Gold/Failure Example + Eligible P4 Candidate -> Teaching Package -> Agent Contract -> Recertification -> Release Eligibility`

The package is a teaching manifest, not mutation authority. It intentionally exposes no API for
fine-tuning, prompt/model replacement, registry mutation, deployment, or production release.

Validated implementation head `c887edf5030f4012b85e4949fcc6200c38352217` passed CI Foundation
on Python 3.11/3.12/3.13, Architectural Audit 1.0, GitHub App Smoke Test, and smoke-dispatched
Stage Gate #219. Because this SSoT update creates a newer docs+code head, that exact final head
must pass the same merge gates before merge.

P5 becomes COMPLETE only after exact-head merge and post-merge validation on `main`.

## P6 — Semantic Self-Healing and Change Propagation

Status: **PLANNED**

Dependency: trustworthy measurement and learning-event diagnosis.

Planned scope:

- semantic KQM failure diagnosis;
- dependency-aware change impact graph;
- selective downstream revalidation;
- candidate repair generation;
- fresh-SHA replay and KQM regression comparison;
- promotion only through existing gates.

Change Propagation must not be represented as dependency-aware while it is merely `run all`.
Safe broad validation remains preferable until the dependency model is trustworthy.

## P7 — Controlled Self-Learning / Adversarial Verification

Status: **PLANNED**

Dependency: P4-P6 must demonstrate safe measured improvement.

Possible scope:

- Generator / Challenger / Evidence Verifier / Reviewer roles;
- multi-agent verification for high-risk reasoning;
- calibrated strategy/model routing;
- automatic bounded improvement experiments;
- promotion of only measured improvements;
- suspension/rollback when regressions exceed policy.

No debate or majority vote can replace source evidence.

## Cross-program blockers that remain explicit

### Extraction production KQM

Still BLOCKED pending independent annotation review, corpus freeze/IAA where required,
quality improvement on development/validation only, and later authorized locked evaluation.

### Reasoning production KQM

Still BLOCKED until the synthetic reasoning corpus is independently reviewed/frozen and the
benchmark is broadened beyond contract-conformance cases to domain-representative reasoning
tasks.

### Real private cases

Must remain local-only and are never required to prove public CI correctness.

## Program completion gate

Every substantive program follows:

`branch -> implementation -> tests -> fresh SHA -> CI/Audit/Smoke -> merge exact head -> post-merge validation`

Ordinary FAIL does not stop the program. It triggers diagnosis, the smallest justified repair,
a fresh SHA, and revalidation. A program stops only for a genuine methodological conflict,
safety/privacy violation, or unresolved dependency that makes truthful continuation impossible.
