# LUKART ROS — Canonical Working Principles

Version: 1.1
Status: Canonical project operating standard
Scope: Repository-wide engineering, agents, automation, reviews, CI/CD, release governance

This document consolidates the previously distributed working rules into one canonical operating standard. It is intentionally stricter than a normal coding guide. The goal is not maximum feature velocity; the goal is increasing trustworthiness, reproducibility, security, recoverability, and auditability.

If a later idea is demonstrably better, it may be added or replace an existing rule through a controlled update to this document. Do not create parallel competing rule lists. Where this document conflicts with an accepted ADR or explicit safety invariant, the stricter safety/trust requirement wins and the conflict must be made explicit.

## 1. End-to-end execution

When an agreed stage, roadmap, audit, repair, or implementation can continue with available tools, execute it automatically from start to finish.

Do not stop merely because:
- a branch was created;
- a commit was created;
- a PR was opened;
- CI is still running;
- a repairable error appeared;
- only part of the matrix is green;
- another obvious technical step remains and requires no user decision.

When a failure occurs:
1. identify the real root cause;
2. make the smallest justified repair;
3. run a focused validation;
4. run the required regression;
5. create a fresh SHA;
6. re-run exact-SHA CI;
7. continue automatically.

Do not ask for confirmation between already-approved sequential steps unless a genuinely new business decision, authorization boundary, or irreversible action appears.

## 2. Canonical delivery pipeline

Default workflow:

`Problem -> Evidence -> Measurement -> Design -> Implementation -> Focused Tests -> Adversarial Tests -> Full Regression -> CI -> Exact-SHA Validation -> PR -> Merge -> Post-Merge Validation -> Evidence -> Closure`

For substantive repository work:
1. verify current `main` and exact baseline SHA;
2. define the decision need and acceptance criteria;
3. identify affected trust/Product/Factory boundaries;
4. implement the smallest sufficient vertical slice;
5. add focused positive and negative tests;
6. add adversarial tests for trust boundaries;
7. run lint, type checks, security/policy gates, and full regression;
8. fix failures without weakening valid gates;
9. validate one exact candidate SHA in CI;
10. merge using the validated head SHA;
11. verify the resulting `main` SHA;
12. execute post-merge validation and inspect release/tag side effects;
13. close the stage only after its Definition of Done is satisfied.

## 3. Fundamental principles

Always apply:

- **Evidence Before Conclusion** — prove before claiming.
- **Decision Need First** — determine what decision actually needs to be made.
- **Problem First** — do not design a solution before defining the problem.
- **Measurement Before Conclusion** — use measurement where measurement is possible.
- **Incremental Validation** — validate important changes as early as practical.
- **Evidence Before Standard** — do not create a rule merely because it feels cleaner.
- **Factory != Product** — infrastructure is not domain truth or Product completeness.
- **Build First, Discuss Only When Necessary** — prefer working, tested evidence over speculative architecture discussion.
- **Single Source of Truth** — do not create competing canonical definitions.
- **Validation Before Trust** — unvalidated material cannot become trusted state.
- **Planned != Implemented != Validated != Certified** — status words are not interchangeable.

## 4. Hardcore Enterprise upgrade rule

Before every major new roadmap or phase, explicitly check whether the plan can be improved to a reasonable Hardcore Enterprise level.

Do not add complexity for prestige. Raise the standard where there is:
- a measured weakness;
- a real trust boundary;
- security exposure;
- data-loss risk;
- non-determinism;
- semantic-regression risk;
- scalability failure;
- recovery/rollback weakness;
- provenance/auditability gap.

Preferred design posture:

`contract-first + adversarial-first + deterministic + bounded + measurable + reversible + provenance-aware + fail-closed`

### Long-Horizon Engineering / 10-Year Design Horizon

For every major architectural, platform, provider, schema, persistence, orchestration, security-boundary, or data-format decision, also evaluate whether the design remains safely evolvable over an indicative 5–10 year horizon.

The goal is **not** to predict which specific technologies will exist in the future. The goal is to avoid present-day decisions that unnecessarily trap trusted data, provenance, replayability, security controls, or audit evidence inside technology that is difficult to replace.

Prefer, where justified:
- versioned and open contracts;
- replaceable components and provider/model independence;
- interoperability and explicit migration paths;
- backward compatibility where practical;
- stable/canonical data representations;
- deterministic replay and provenance identities that survive component replacement;
- rollback and recovery paths;
- bounded vendor and technology lock-in;
- preservation of evidence, auditability, and epistemic controls across technology changes.

For a material long-horizon decision, explicitly ask:
1. What concrete future change would make the current design expensive or unsafe to replace?
2. Can a model, provider, database, schema, renderer, orchestration layer, or infrastructure component be replaced without losing trusted data, evidence provenance, replay identity, auditability, or security invariants?
3. Is compatibility/migration explicit and testable?
4. Is rollback/recovery possible if the replacement fails?
5. Does the proposed abstraction solve a credible failure mode or change cost, rather than a hypothetical future possibility?

Do not use a 5–10 year horizon as justification for speculative frameworks or generalized abstractions without a concrete failure mode, trust boundary, migration risk, or measurable future-change cost.

Short rule: **future-resistant, not future-predictive**.

Important capabilities should, where justified, include:
- explicit contracts and invariants;
- negative and adversarial tests;
- deterministic behavior;
- bounded resources;
- audit trail and provenance;
- replayability;
- compatibility guarantees;
- rollback or verified recovery.

## 5. Epistemic and trust boundaries

No agent, plugin, self-healing mechanism, learning pipeline, renderer, telemetry subsystem, or automated experiment may establish truth by itself.

Canonical trust chain:

`Evidence -> Epistemic State -> Reasoning -> Validation -> Trusted Result`

Automation must not:
- promote uncertain content to `FACT` without required evidence;
- hide contradictions;
- remove open questions merely to obtain PASS;
- modify locked Gold/evaluation data to improve scores;
- self-certify its own independent review;
- bypass a trust gate;
- treat model output as epistemic authority.

When evidence is insufficient, prefer explicit `UNKNOWN`, `UNRESOLVED`, or `ABSTAIN` rather than forced certainty.

## 6. Fail-closed default

Unknown or invalid trust-boundary state must fail closed.

Examples include unknown or invalid:
- schema version;
- provider/plugin identity;
- capability;
- credential;
- evidence hash;
- provenance record;
- migration path;
- API major version;
- attestation;
- authorization state.

Do not silently downgrade validation or accept unknown state for convenience.

## 7. Determinism, provenance, and replay

Critical artifacts should be, where practical:
- canonically serialized;
- digest-bound;
- content-addressed;
- replayable;
- bound to exact code/configuration identity.

Replay identity should include, where applicable:

`code SHA + config digest + corpus digest + schema version + provider/plugin versions + input/evidence digests`

Do not call a run an identical replay when influential identity is unknown.

Separate semantic change from textual/code-format change. Presentation-only change must not automatically be treated as analytical change.

## 8. Compatibility and migrations

Migrations must be:
- explicitly versioned;
- deterministic;
- idempotent where reasonably possible;
- tested against old data;
- fail-closed for unknown migration routes;
- explicit about semantic changes.

Do not create a parallel second authority for logic that can be safely extended in the existing canonical mechanism.

## 9. Security engineering

Apply defence in depth and least privilege.

Prefer:
- deny-by-default authorization;
- capability-based access;
- tenant/case isolation;
- short-lived credentials;
- explicit timeout and cancellation;
- bounded concurrency;
- key rotation and revocation;
- tamper detection;
- audit trail;
- environment/input sanitization.

Do not call logical or process separation a kernel/container sandbox unless the claimed isolation actually exists.

Do not claim compliance/certification with an external standard merely because the implementation is inspired by that standard.

## 10. Supply chain and CI

Prefer and progressively enforce:
- external GitHub Actions pinned to immutable full commit SHA;
- dependency auditing;
- SBOM generation;
- build provenance;
- SAST/CodeQL;
- secret scanning;
- PII/confidentiality gates;
- dependency-boundary checks;
- reproducible or tightly controlled build environments.

All required gates for a certification or merge decision must refer to the same exact candidate SHA.

Never assemble a green certification claim from results belonging to different commits.

## 11. Performance and scalability

Do not optimize from intuition alone.

Use:
1. measurement;
2. profiling;
3. explicit budget/limit;
4. targeted improvement;
5. re-measurement.

Test meaningful size classes such as small, medium, large, and certification/stress.

Measure where relevant:
- runtime;
- peak memory;
- cache behavior;
- concurrency;
- blast radius;
- replay;
- graph traversal and propagation.

Avoid algorithmic behavior that becomes structurally unacceptable at realistic production sizes. Do not rely on brittle wall-clock thresholds in normal shared CI when deterministic work-based assertions are possible.

## 12. Agent runtime and plugins

An agent is a bounded capability worker, not a source of truth.

Agent runtime should provide, as applicable:
- capability routing;
- maximum steps/work budget;
- timeout;
- cancellation;
- concurrency limits;
- provider identity/version;
- audit records;
- deterministic fallback;
- health/circuit-breaker state.

Plugin registries should:
- store classes/definitions rather than live global instances;
- expose explicit versions and capabilities;
- reject duplicate identities;
- provide deterministic discovery;
- never grant undeclared permissions.

## 13. Controlled learning and self-healing

Allowed promotion lifecycle:

`Failure -> Candidate -> Experiment -> Validation -> Promotion -> Monitoring -> optional Rollback`

There is no direct path:

`Candidate -> Trusted`

Self-healing may diagnose and propose/implement a bounded repair inside approved scope, but must not expand its own trust authority.

Locked evaluation/Gold must not be used as a tuning target or silently mutated to obtain PASS.

## 14. Human review and certification honesty

Never fabricate:
- human review;
- independent review;
- security review;
- red-team review;
- external certification.

Automated evidence may support **ENGINEERING PASS**, but not an independent certification claim without real independent evidence.

Use explicit states such as `INDEPENDENT_REVIEW_REQUIRED` when engineering validation is complete but independent review has not occurred.

Do not revive historical closed review blockers as new current-roadmap blockers unless the new roadmap explicitly depends on them.

## 15. Baseline and release immutability

A closed release is a historical artifact.

Do not mutate an old baseline/tag simply because current development continues.

Keep distinct:
- historical release version;
- development intent/version;
- explicit release intent.

A development run must not accidentally move a historical tag or publish a release. Release mutation requires explicit release intent and exact-SHA validation.

## 16. Git/GitHub workflow

Default model:

`main -> branch -> commits -> tests -> PR -> exact-SHA CI -> merge -> post-merge validation`

Before changes:
- verify current `main` SHA;
- branch from the intended baseline.

After any repair:
- create a fresh SHA;
- validate that fresh SHA.

Merge only when required exact-SHA gates are green and the PR head has not moved after validation. Prefer an expected-head-SHA guard when supported.

After merge verify:
- actual `main` SHA;
- post-merge workflows;
- release side effects;
- historical tag immutability;
- regressions.

## 17. Definition of Done

A stage is DONE only when all applicable elements are complete:
- implementation finished;
- focused tests PASS;
- adversarial tests PASS;
- full regression PASS;
- lint PASS;
- type-check PASS;
- security/policy gates PASS;
- exact-SHA CI PASS;
- PR merged;
- resulting `main` verified;
- post-merge validation PASS;
- historical baseline/release unaffected unless intentionally changed;
- required evidence bundle exists;
- no repairable blocker remains inside the agreed scope.

Creating code, opening a PR, or obtaining partial green CI is not DONE.

## 18. Communication during long work

Short progress updates are allowed and useful for material findings, root causes, or state transitions, but they are not stage closure.

Do not stop execution merely to provide an intermediate report when tools can continue the agreed work.

Ask the user only when:
- indispensable information is missing;
- there are materially different business decisions;
- user authorization is required;
- an unapproved irreversible action would otherwise occur.

When a safe, reasonable engineering assumption is available, make it explicit if material and continue.

## 19. Final reporting

Only after complete stage closure provide a short final report containing:

### STATUS
`DONE / PASS / BLOCKED`

### EXECUTED
The most important completed items.

### FINAL STATE
- final `main` SHA;
- PR/merge state;
- key gates/tests;
- release/baseline state.

### CONCLUSION
A few sentences only.

### NEXT
A short ordered task list.

Avoid long conclusion sections after intermediate technical steps.

## 20. Roadmap execution

When the user has approved an ordered roadmap such as `P3-01 -> P3-10`, `E0 -> E10`, or `H1 -> H10`, execute it automatically in that order.

Before implementation:
1. verify live repository state;
2. review the roadmap for avoidable weakness;
3. upgrade it to a justified Hardcore Enterprise level;
4. apply the Long-Horizon Engineering / 10-Year Design Horizon check to major architectural decisions;
5. execute the improved roadmap end-to-end.

Do not stop between roadmap items unless a genuine blocker requires user action.

After closure, summarize and propose the next logical track.

## 21. Living-standard amendment rule

This document is a living canonical standard, not a frozen checklist.

A new principle may be added when it materially improves correctness, epistemic safety, determinism, security, provenance, replayability, resilience, observability, recoverability, auditability, or long-term evolvability.

Before adding a new rule:
1. identify the concrete failure mode or risk it addresses;
2. check whether an existing rule already covers it;
3. prefer merging/refining an existing rule over duplication;
4. ensure the new rule does not weaken a safety invariant;
5. update this canonical document rather than creating another competing list;
6. update related `AGENTS.md`, ADR, CI policy, or tests only when the rule requires executable enforcement.

The target is one coherent operating system for engineering behavior, not an ever-growing pile of overlapping instructions.

## 22. North-star objective

The purpose of LUKART ROS is not to maximize the number of features.

The purpose is to create a system that becomes more trustworthy when:
- data is incomplete;
- evidence conflicts;
- a source is wrong;
- an input is malicious;
- infrastructure partially fails;
- code/schema/providers change;
- workload size increases.

Every major evolution should increase:

`correctness + epistemic safety + determinism + security + provenance + replayability + resilience + observability + recoverability + auditability + evolvability`

without unjustified complexity.

Major evolutions should also preserve the ability to replace technology without losing trusted data, evidence provenance, replay identity, auditability, security boundaries, or epistemic controls.
