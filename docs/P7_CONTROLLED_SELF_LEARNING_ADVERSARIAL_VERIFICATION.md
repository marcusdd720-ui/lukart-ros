# P7 — Controlled Self-Learning / Adversarial Verification

Status: VALIDATED IMPLEMENTATION / FINAL MERGE GATE PENDING

## Decision need

P4 can turn measured failures into bounded experiments and measured promotion decisions. P6 can
diagnose semantic failures, compute trustworthy revalidation impact, and require fresh-SHA
Replay/KQM evidence before an improvement may continue through the existing promotion/release path.

P7 adds the missing governance layer before and around that loop: independent adversarial
verification of a proposed subject and a controlled closure proving that one verified measured
failure traversed the existing P4-P6 learning path without acquiring direct mutation authority.

The P7 v1 loop is:

`Generator -> Challenger(s) -> Evidence Verifier -> Reviewer -> Adversarial Verification Decision`

For a measured learning trigger:

`VERIFIED MeasuredFailure -> P4 LearningCandidate -> bounded Experiment -> P4 Promotion -> P6 Fresh-SHA Readiness -> P7 Self-Learning Cycle Decision`

P7 is fail-closed. It does not patch source, rewrite prompts/models, mutate registries, merge, deploy,
or release Product state.

## P7.1 — Independent adversarial roles

A `VerificationProposal` binds one generator identity to an exact subject digest, claim digests, and
evidence digests. `ChallengeAssessment`, `EvidenceVerification`, and `ReviewAssessment` are separate
immutable artifacts bound to the exact proposal digest.

Generator, every Challenger, Evidence Verifier, and Reviewer must use independent identities.
Duplicate challenger identities or self-review/self-verification cause REJECTED.

## P7.2 — Evidence beats votes

`AdversarialVerificationGate` intentionally contains no vote counter, majority threshold, or consensus
rule. Supportive agents cannot override:

- rejected provenance/evidence;
- an unsupported claim;
- an upheld blocking challenge;
- missing independent evidence verification;
- failed independent review.

The Evidence Verifier has an asymmetric veto over unsupported truth claims. This is a governance
asymmetry, not an agent-confidence heuristic.

## P7.3 — Blocking challenge resolution

Every blocking challenge must be resolved explicitly by the independent Evidence Verifier. A
resolution is bound to the challenge code and cites evidence that was independently checked.

Possible resolution states are:

- `RESOLVED` — evidence answers the challenge;
- `UPHELD` — the challenge is supported and the proposal is REJECTED;
- `INCONCLUSIVE` — evidence is insufficient and the proposal remains INCONCLUSIVE.

An unknown challenge resolution, unchecked resolution evidence, duplicate challenge code, or a
challenge against a claim outside the proposal is rejected fail-closed.

## P7.4 — Calibrated abstention

A proposal is `VERIFIED` only when:

1. all role identities are independent;
2. every artifact is bound to the exact proposal;
3. every proposal evidence digest was independently checked;
4. no evidence was rejected;
5. no proposal claim was declared unsupported;
6. every blocking challenge was evidence-resolved;
7. Evidence Verification is PASS;
8. independent Review is PASS.

Missing evidence checks, unresolved blocking challenges, or inconclusive independent assessment
produce `INCONCLUSIVE`, not guessed truth.

## P7.5 — Controlled self-learning closure

`ControlledSelfLearningGate` accepts only an adversarial verification whose subject type is exactly
`measured_failure` and whose subject digest equals the exact `MeasuredFailure.digest()`.

It then verifies exact bindings across the already-governed path:

1. MeasuredFailure -> Adversarial Verification;
2. MeasuredFailure -> P4 LearningCandidate;
3. LearningCandidate -> P4 ExperimentContract;
4. ExperimentContract -> P4 PromotionDecision;
5. LearningCandidate -> P6 RepairReadinessDecision.

P7 does not create a parallel candidate, experiment, promotion, replay, or release authority.

## P7.6 — Regression suspension

If a P4 metric delta exceeds its declared regression guardrail, the P7 cycle returns `SUSPENDED`.
This prevents a measured regression from being treated as an ordinary unsuccessful vote or from
continuing automatically through the learning path.

Other outcomes are:

- `READY_FOR_EXISTING_RELEASE_PATH`;
- `REJECTED`;
- `INCONCLUSIVE`.

`READY_FOR_EXISTING_RELEASE_PATH` is not deployment authority. It says only that the exact verified
learning cycle may continue through existing controlled release mechanisms.

## P7.7 — Locked evaluation remains protected

P7 reuses P4 `ExperimentContract`. Therefore only `development` and `validation` splits are legal
learning inputs. `locked_evaluation` remains prohibited for tuning/learning and is covered by the P7
adversarial test suite.

## Adversarial tests

The P7 test suite verifies at minimum:

1. independent roles can produce VERIFIED only after evidence-bound blocking-challenge resolution;
2. multiple supportive challengers cannot override an Evidence Verifier veto;
3. unresolved blocking challenge -> INCONCLUSIVE;
4. upheld blocking challenge -> REJECTED;
5. generator/verifier identity collision -> REJECTED;
6. incomplete evidence checking -> INCONCLUSIVE;
7. unknown challenge resolution -> REJECTED;
8. verified measured failure + exact P4/P6 bindings -> READY_FOR_EXISTING_RELEASE_PATH;
9. measured guardrail regression -> SUSPENDED;
10. inconclusive adversarial trigger cannot enter a successful self-learning cycle;
11. `locked_evaluation` remains prohibited.

## Observed FAIL -> repair evidence

Initial feature head `15b7017599eb` (abbreviated Git SHA) passed dependency boundary, secret
scanning, model usage audit, dead-code inventory, and Architectural Audit, but CI stopped in Ruff
before Mypy/Pytest because two new source lines exceeded the repository 100-character limit.

The first repair changed formatting only. No P7 decision semantics, evidence rules, P4/P6 bindings,
or test expectations were relaxed.

Fresh repair head `a2d7bbdf73c0` (abbreviated Git SHA) then passed:

- CI Foundation on Python 3.11, 3.12, and 3.13;
- Ruff, Mypy, pytest, dependency boundary, secret scan, model usage audit, and repository gates;
- Architectural Audit 1.0;
- GitHub App Smoke Test;
- smoke-dispatched Stage Gate #234.

The first docs+code finalization head `de74d16d` exposed a second fail-closed event. Ruff passed,
Mypy reported no issues in 392 source files, all 478 pytest tests passed, and Repository Audit passed,
but the PII/confidentiality gate rejected this document because the full hexadecimal Git SHA strings
above happened to contain decimal runs matching the repository's NIP-like pattern. No PII was
present. The scanner was not weakened or allowlisted; public SSoT references were changed to
abbreviated Git SHA values while exact full hashes remain auditable in Git and PR history.

This documentation repair creates a newer docs+code feature head. That exact final head must pass the
same merge gates before merge. P7 remains incomplete until exact-head merge and post-merge validation
succeed.

## Non-goals

P7 v1 does not:

- let agents vote truth into existence;
- permit self-review or self-verification where independence is required;
- generate/apply source patches automatically;
- rewrite prompts, models, routing, retrieval, policies, or canonical knowledge automatically;
- train/fine-tune a model directly;
- use locked evaluation for tuning;
- bypass P4 PromotionGate or P6 fresh-SHA readiness;
- merge, deploy, or release production state;
- claim that domain reasoning quality is production-certified.

Calibrated model/strategy routing and autonomous generation of candidate implementations remain
future extensions and must reuse the same measured/evidence gates rather than weaken them.

## Definition of Done

P7 becomes COMPLETE only when:

1. adversarial verification contracts and gate tests pass;
2. majority-vote, self-review, provenance-veto, unresolved-challenge, and abstention tests pass;
3. controlled self-learning exact-binding and regression-suspension tests pass;
4. locked evaluation remains prohibited;
5. full Ruff/MyPy/pytest and repository gates pass;
6. Architectural Audit passes;
7. GitHub App Smoke Test and its dispatched Stage Gate pass on the exact final feature head;
8. exact validated feature head is merged to `main`;
9. post-merge CI, Architectural Audit, Stage Orchestrator, Smoke, and dispatched Stage Gate pass;
10. SSoT records P7 COMPLETE without claiming autonomous production self-modification.
