# Night Shift Autonomous Engineering Fabric v2

Status: ARCHITECTURE CANDIDATE / SHADOW-FIRST
Date: 2026-09-28
Horizon: 15+ years

## Executive decision

Do not make Temporal, DBOS, LangGraph, GitHub Actions, Codex, Work, Claude, Llama or any other vendor/runtime the architectural core.

The sovereign core is a set of versioned contracts and evidence:
- Policy;
- Live State Snapshot;
- Task Capsule;
- Authority Envelope;
- Lease;
- Execution Receipt;
- Verification Verdict;
- Promotion Decision.

Everything else is an adapter.

## Primary objective

Maximize independently verified useful closure per unit of calendar time, compute, quota and human intervention.

Code volume, agent activity and number of branches are not success metrics.
## Critical correction to v1

Policy and live project state must never share one authority object.

POLICY is slow-changing and versioned.
LIVE STATE is observed, short-lived and content-addressed.
QUEUE is derived.

Canonical rule:

PolicyHash + StateSnapshotHash + TaskContractHash
-> DecisionHash
-> Execution
-> Evidence
-> Verification
-> Promotion

A stale state snapshot cannot authorize mutation.

## Five planes

1. Sovereign Control Plane
2. Durable Execution Plane
3. Isolated Execution Plane
4. Verification and Evidence Plane
5. Promotion and Identity Plane

No plane may silently assume authority owned by another plane.
## Sovereign Control Plane

Own:
- schemas;
- policy;
- risk classes;
- resource limits;
- state transition rules;
- task identity;
- evidence obligations.

Do not own:
- model implementation;
- GitHub implementation;
- workflow-engine implementation;
- CI vendor implementation.

The control plane must operate if every current AI provider changes.

## Live State Plane

Every observation produces an immutable StateSnapshot:
- repository;
- branch;
- base SHA;
- head SHA;
- PR;
- CI;
- dirty state;
- runner state;
- dependency state;
- observed_at;
- source evidence.

Snapshots expire by policy.
UNKNOWN or conflicting critical state fails closed.
## Durable Execution Plane

Expose a provider-neutral DurableWorkflowEngine interface.

Required semantics:
- durable checkpoint;
- restart recovery;
- retries and deadlines;
- idempotent activity identity;
- cancellation;
- replay;
- quarantine;
- durable timers.

Initial implementation recommendation:
- DBOS as the lightweight pilot candidate on the current workstation;
- Temporal as the high-assurance scale reference;
- other engines remain benchmark candidates.

Reason: DBOS can checkpoint workflows in Postgres/SQLite without requiring a separate orchestration service, while Temporal has a strong event-history/replay model for larger distributed execution.

The engine is replaceable. Its database schema is not the business contract.
## Isolated Execution Plane

Every mutable task receives:
- dedicated worktree or ephemeral clone;
- dedicated branch;
- lease_id;
- fencing_token;
- worker_id;
- task capsule hash;
- restricted filesystem scope;
- restricted credential scope.

Persistent validation runners must not become autonomous coding workspaces.

Prefer ephemeral/JIT validation runners for higher-risk work when practical.

The owner's interactive worktree is never an autonomous mutation target.

## Lease and fencing

Only the newest valid fencing token may:
- push;
- update canonical task state;
- freeze a candidate;
- request promotion.

Expired workers are permanently stale.
Canonical updates use compare-and-swap.
## Authority Envelope

Every unattended window requires an immutable AutonomyEnvelope.

It defines:
- repositories and task classes;
- path boundaries;
- maximum change scope;
- task and retry limits;
- model and compute budgets;
- promotion authority;
- signing policy;
- expiry;
- stop conditions.

A worker may consume authority but may never expand it.
Authority expires automatically.

## Risk classes
R0 deterministic/non-semantic: eligible for automatic promotion after all gates.
R1 bounded low-risk code: pre-authorized automatic promotion only.
R2 product/domain behavior: build/test/review automatically; normally READY_FOR_HUMAN.
R3 security/auth/governance/legal authority: no unattended promotion.
R4 destructive/financial/external-account action: human mandatory.
## Verification Quorum

No single model may both create and certify a non-trivial candidate.

Promotion evidence is a quorum rather than one verdict.

Example R2 quorum:
- deterministic focused tests PASS;
- static and security gates PASS;
- full required regression PASS;
- independent reviewer PASS;
- exact-SHA CI PASS;
- policy engine PASS.

For higher risk, use heterogeneous verification where useful:
- builder A;
- reviewer B or deterministic specialist;
- human authority for R3/R4.

Model disagreement is evidence, not noise.
## Causal Gate Graph

Downstream failures inherit BLOCKED_BY(root_cause_id).

The scheduler remediates the root cause rather than every red dashboard item.

## Evidence Plane

Every attempt produces an ExecutionReceipt containing:
- task_id;
- state_snapshot_hash;
- policy_hash;
- authority_envelope_hash;
- task_capsule_hash;
- lease and fencing identity;
- input SHAs;
- diff hash;
- environment fingerprint;
- executor identity;
- validation evidence;
- review verdict;
- CI run IDs;
- output SHA;
- final state;
- elapsed/resource metrics.
Execution receipts are append-only and content-addressed.

A future provider must be able to verify an old receipt without contacting the original model provider.

## Identity separation

Separate HUMAN_IDENTITY from AUTOMATION_IDENTITY.

The human identity remains root-of-trust and is not available to unattended workers.

Automation identity must be:
- repository-scoped;
- rotatable;
- revocable;
- limited to machine actions allowed by policy.

Prefer short-lived workload credentials where available.

Use a portable signed-attestation format while retaining offline verification.
## Reproducible environment

Exact source SHA is insufficient when environment drift is uncontrolled.

Every receipt should bind:
- OS/runtime version;
- dependency lock hashes;
- container or image digest when used;
- compiler/interpreter version;
- relevant environment-policy version.

Dagger or equivalent containerized validation is an optional portability adapter.

Do not introduce heavyweight environment tooling until measured drift justifies it.

## Observability

Use one trace identity across scheduler, worker, CI, reviewer and promotion.

OpenTelemetry-compatible context is preferred as an adapter.

Logs are diagnostic.
Execution receipts are authority.
## Counterfactual Shadow Twin

Before autonomous promotion is trusted, run the scheduler in SHADOW mode.

For each real human-driven task:
- predict selected task;
- predict executor;
- predict stop or escalation;
- compare prediction with actual outcome;
- record counterfactual error.

Promotion to higher autonomy requires measured calibration.

This allows self-improvement without allowing the learning system to silently rewrite governance.

## Autonomy Debt

Track AUTONOMY_DEBT: automation behavior not yet supported by replayable evidence.

New autonomous capability consumes debt budget.
Repeated validated success retires debt.
Unexplained divergence increases debt.

If debt exceeds policy threshold, downgrade to SHADOW or HUMAN mode.
## Failure injection requirement

Before unattended pilot, test:
- worker termination during edit;
- worker termination during validation;
- scheduler restart after dispatch;
- duplicate event delivery;
- stale worker resumption;
- network loss during push;
- delayed CI;
- concurrent branch advance;
- disk pressure;
- corrupted receipt;
- reviewer timeout.

PASS requires deterministic recovery or fail-closed stop.

## Morning output

CLOSED
READY_FOR_HUMAN
BLOCKED
QUARANTINED
BUDGET
EVIDENCE

Narrative-only "mostly done" is not a valid state.
## Recommended implementation order

V2-00 separate Policy from Live State.
V2-01 version schemas and content hashes.
V2-02 event journal and inbox/outbox.
V2-03 leases, fencing and CAS.
V2-04 isolated worktree manager.
V2-05 DBOS pilot adapter.
V2-06 scheduler and resource governor.
V2-07 GitHub/runner adapter.
V2-08 executor adapters.
V2-09 verification quorum.
V2-10 automation identity and receipt signing.
V2-11 causal gate graph.
V2-12 shadow twin and autonomy debt.
V2-13 failure-injection suite.
V2-14 controlled night pilot.
V2-15 benchmark DBOS versus Temporal before scale promotion.

## Core invariant

The product is not the agent.

The product is the verifiable transition:
KNOWN STATE -> AUTHORIZED TASK -> ISOLATED EXECUTION -> INDEPENDENT EVIDENCE -> POLICY-VALID PROMOTION -> REPLAYABLE CLOSURE.
