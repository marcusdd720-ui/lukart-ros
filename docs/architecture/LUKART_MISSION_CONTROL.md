# LUKART Mission Control — Human Supervision & Cooperative Agent Control Plane

Status: **ARCHITECTURE CANDIDATE / ADOPT-FIRST**
Date: 2026-10-06
Base SHA: `c4419692c318862d42b7cf5f8f0265e54b5511f2`

## 1. Problem statement

LUKART currently has capable components — GitHub Actions, self-hosted runners, provider radars, automations, Codex/Hermes/Aider-class executors, exact-SHA gates and project-specific evidence — but no single durable control plane that owns the full lifecycle of work across projects and agents.

Observed failure mode on 2026-10-06:

- Generator Pism PR #57 current candidate: `ce1096d6232cc89f6f3457f334da62f5f4e9948b`;
- mandatory workflows for the current candidate were queued;
- the only self-hosted runner was still executing superseded SHA `d86a42754cd4a60b1f46485855c5e479cdcc3707`;
- the system detected failure/state, but no durable remediation owner automatically converted it into repair → fresh SHA → exact-SHA rerun;
- human-visible status did not reliably distinguish PLAN, QUEUED, EXECUTING, ADVANCING, STALLED, BLOCKED, VERIFYING and HUMAN_REQUIRED.

The primary weakness is therefore **not model intelligence**. It is the absence of a durable, authoritative, vendor-neutral **execution truth + coordination + human supervision plane**.

## 2. Non-negotiable architecture principle

Do not build commodity orchestration, dashboards, telemetry, agent communication, queueing or retry systems from scratch.

Decision sequence:

`REUSE INTERNAL → ADOPT → WRAP → EXTEND → FORK → BUILD ONLY MISSING LUKART DELTA`

The LUKART-specific delta is:

- product/portfolio priority policy;
- TaskSpec and AcceptanceContract;
- immutable candidate/evidence identity;
- exact-SHA promotion gates;
- Evidence Before State;
- human/legal authority boundaries;
- provider/capability routing policy;
- Recovery Genome / verified learning;
- cross-project progress model;
- conformance and chaos tests.

## 3. ADOPT decision

### PRIMARY POC — Hatchet

Classification: **ADOPT / POC FIRST**

Why:
- open-source MIT;
- self-hostable;
- PostgreSQL-backed durable execution;
- durable tasks and workflows;
- retries, timeouts, dependencies, concurrency and worker slots;
- worker labels/affinity for capability routing;
- built-in dashboard, run history, logs and replay;
- suitable for long-running AI agent workloads.

LUKART must wrap Hatchet behind an internal `DurableExecutionAdapter`. Hatchet is replaceable substrate, never product truth.

### Hermes Kanban

Classification: **ADOPT AS AGENT COORDINATION LANE / REFERENCE**, not global SSOT.

Use:
- coding-agent worker lanes;
- task/review/block/handoff semantics;
- heartbeat and stale-worker concepts;
- circuit breaker and retry patterns;
- durable handoff summaries;
- Codex/Claude/OpenCode/Hermes-style executor adapters.

Do not make the local SQLite board the cross-cloud enterprise authority.

### A2A 1.0

Classification: **ADOPT AS AGENT-TO-AGENT INTEROPERABILITY PROTOCOL**.

Use Agent Cards for capability discovery and A2A Task/Message/Artifact semantics for:
- help requests;
- specialist escalation;
- handoff;
- progress/status updates;
- artifact exchange;
- asynchronous long-running collaboration.

MCP remains a tool/resource protocol. A2A is the preferred inter-agent boundary.

### OpenTelemetry

Classification: **ADOPT**.

Use for provider-neutral spans, events, metrics and logs. LUKART-specific attributes may extend the standard but must not replace it.

### Grafana OSS

Classification: **ADOPT AS HUMAN SINGLE PANE OF GLASS**.

Do not build a custom dashboard first.

Grafana reads a canonical Mission Control read model and shows:
- portfolio status;
- per-project progress;
- agent health;
- active runs;
- stale/no-progress runs;
- queue age;
- provider quota/capacity;
- CI state;
- verification backlog;
- blockers;
- next task;
- human gates.

### Langfuse OSS

Classification: **ADOPT / OPTIONAL PHASE 2**.

Use for agent/LLM trace, sessions, evaluations and agent graphs where deeper model-level observability is needed. It is not the task scheduler or product SSOT.

### Temporal

Classification: **REFERENCE / FALLBACK BENCHMARK**.

Use as the reliability ceiling and alternate backend if Hatchet fails LUKART conformance, soak or scale requirements.

### DBOS

Classification: **RUNTIME CANDIDATE / NOT PRIMARY CONTROL PANEL UNDER 0 PLN**.

Open-source DBOS durable runtime remains a valid backend candidate. Production self-host of DBOS Conductor/Console requires a commercial license, so it is not the preferred zero-cost Mission Control plane.

## 4. Target architecture

```
HUMAN
  ↓
Grafana Mission Control
  ↓
LUKART Portfolio / Policy / Evidence Read Model
  ↓
LUKART Control Plane
  ├── Project DAG + priorities
  ├── TaskSpec + AcceptanceContract
  ├── Agent Capability Registry
  ├── Provider/Compute Capacity Registry (LEX)
  ├── Recovery Genome
  ├── Human Gate Engine
  └── Evidence / Candidate Identity
  ↓
DurableExecutionAdapter
  ↓
Hatchet POC ─────────────── Temporal fallback/reference
  ↓
Agent Execution Pools
  ├── Codex lane
  ├── Hermes lane
  ├── Aider/OpenCode lane
  ├── deterministic CI/test lane
  └── future A2A-compatible agents
  ↓
Git worktrees / CI / artifact stores / providers
  ↓
Execution Receipts + OTel + GitHub evidence
  ↓
Independent Verifier
  ↓
Promotion Gate
```

## 5. Human panel model

Every project row MUST show:

- project priority;
- accepted scope version;
- verified completion percentage;
- current task;
- current task owner;
- builder;
- verifier;
- provider/model;
- executor/host/cloud;
- exact task/run/attempt IDs;
- exact Git SHA/worktree;
- lifecycle phase;
- liveness state;
- progress state;
- last meaningful progress timestamp;
- retry count/budget;
- blocker;
- requested help;
- next deterministic task;
- CI/gate state;
- human decision required, if any;
- cost/quota risk.

### No fake percentages

Progress is evidence-derived, not model-estimated.

`ProjectProgress = Σ(weight of acceptance criteria with VERIFIED evidence) / Σ(weight of accepted scope criteria)`

A criterion contributes 0 until its verifier accepts exact evidence.

Show three separate values:

1. **Product completion %** — verified accepted scope.
2. **Current execution %** — objective milestones inside the active task.
3. **Promotion readiness %** — mandatory release gates passed.

Do not infer ETA until enough historical run data exists to support a confidence interval.

## 6. Agent roles — dynamic quorum, not fixed “two agents”

The previous idea “2 agents per project” is directionally correct for role separation, but should not be a hard resource allocation rule.

Minimum for mutating/high-risk work:

- **Builder** — writes implementation;
- **Verifier** — independent review/test/evidence.

Optional on demand:

- **Repair Agent** — bounded remediation;
- **Specialist Agent** — narrow capability help;
- **Security Agent**;
- **Integrator**;
- **Promoter** — separate authority.

Rule: Builder != Verifier != Promoter.

A project does not permanently reserve two agents while idle. The scheduler allocates roles dynamically from shared pools.

## 7. Four-cloud concept — corrected

Do not require exactly four clouds to be active at all times.

Target:

- at least **4 configured execution lanes/providers** capable of different workloads;
- at least **2 independent failure domains** for P0/P1 work;
- provider-neutral routing;
- no paid fallback;
- capacity/quota evidence before dispatch;
- no single provider is product truth.

The control plane chooses the fastest compatible zero-cost lane based on capability, availability, trust, expected completion and quota scarcity.

## 8. Cooperative help protocol

An agent MUST NOT silently loop when it is failing.

Emit a structured `HelpRequest` when any trigger fires:

- repeated same failure fingerprint;
- retry budget threshold;
- context/tool budget threshold;
- no meaningful progress threshold;
- missing capability;
- unavailable provider/resource;
- low-confidence high-risk change;
- test failure outside assigned scope.

HelpRequest fields:

- task_id / run_id / attempt_id;
- exact SHA/worktree;
- failing invariant/check;
- normalized error fingerprint;
- attempts already made;
- evidence references;
- current hypothesis;
- requested capability;
- security/privacy scope;
- forbidden shortcuts;
- remaining budget.

Routing:

`HelpRequest → Capability Registry → qualified available agent → A2A handoff → isolated assistance → evidence → builder/integrator decision`

Never let two agents concurrently mutate the same worktree. Assistance is read-only or uses a separate worktree/patch artifact.

## 9. Cooperative learning without poisoning

Agents do not “learn” by blindly copying another agent's conclusion.

They exchange:

- Execution Receipts;
- Repair Records;
- test evidence;
- failure fingerprints;
- successful remediation patterns;
- skill/procedure candidates.

Recovery confidence:

- R0 OBSERVED
- R1 REPRODUCED
- R2 REPAIRED
- R3 VERIFIED
- R4 REUSABLE after success in a second independent incident
- R5 CERTIFIED after chaos/restart/replay evidence

Only R3+ may be recommended automatically.
Only R4+ may be auto-applied within matching preconditions and bounded blast radius.

The model may propose a new skill. A separate curator/verifier admits it.

## 10. Next-task generation

The next task MUST be derived, not narrated.

Inputs:

- accepted Project DAG;
- dependency completion;
- current P0/P1 findings;
- gate state;
- resource/capability availability;
- provider quotas;
- locks/leases;
- current portfolio priority.

Output:

- exactly one `NEXT` per sequential lane;
- optional parallel READY tasks when they do not share mutable authority;
- explicit reason why each task is READY/BLOCKED/HUMAN_REQUIRED.

## 11. Human authority taxonomy

The system should stop asking the human for routine recoverable operations.

### AUTO
- read-only inspection;
- rerun/retry inside bounded policy;
- cancel superseded work;
- switch compatible zero-cost provider;
- generate deterministic evidence;
- start verifier;
- create bounded repair branch/worktree.

### POLICY-GATED AUTO
- apply previously R4+ recovery;
- reassign agent;
- change worker lane;
- start additional verifier;
- quarantine bad provider/run.

### HUMAN REQUIRED
- merge/promotion/release where policy requires explicit approval;
- paid usage;
- legal/client authority;
- irreversible destructive action;
- material product-scope change;
- credential/billing/security-boundary change;
- unresolved ambiguity outside delegated policy.

## 12. Execution truth

A task is not RUNNING because a model says so.

Authoritative execution needs compatible evidence:
- durable task/run id;
- current lease/fencing token;
- live worker/executor identity;
- process/remote-job evidence;
- recent heartbeat;
- recent meaningful progress;
- exact source/worktree identity.

Heartbeat without progress = LIVE/STALLED, not ADVANCING.

## 13. P0 incident rules

Current issue class:
- stale/superseded SHA consumes the only executor;
- current candidate queues behind obsolete work;
- duplicate push + PR validation can consume capacity;
- terminal CI failure does not automatically create a remediation owner.

First remediation MUST adopt native capabilities before custom code:
- GitHub Actions concurrency groups;
- cancel-in-progress;
- bounded timeouts;
- dedup push/PR validation;
- stale candidate rejection;
- Hatchet durable owner for repair/retry lifecycle.

## 14. Deployment sequence

### MC-00 — Current P1 closure
Do not delay Generator Pism v1.0 to build Mission Control.

### MC-01 — Read-only Mission Control
- canonical Project/Task/Run read model in PostgreSQL;
- ingest GitHub PR/CI + LEX provider state + active automation state where available;
- Grafana dashboard;
- no mutation authority.

### MC-02 — Hatchet POC
One narrow real workflow:
`TaskSpec → Builder → Tests → Verifier → exact-SHA CI → promotion gate`

Fault injection:
- worker crash;
- stale worker;
- superseded candidate;
- duplicate dispatch;
- provider outage;
- retry exhaustion.

### MC-03 — Cooperative agents
- A2A Agent Cards;
- HelpRequest;
- dynamic role assignment;
- Hermes/Codex/Aider worker adapters;
- isolated worktrees;
- reviewer separation.

### MC-04 — Recovery Genome
- failure fingerprinting;
- verified remediation records;
- R0–R5 learning lifecycle;
- auto-apply only R4+ bounded recoveries.

### MC-05 — Full human command
- controlled pause/resume/reassign/quarantine;
- policy-gated actions;
- portfolio priorities;
- predictive capacity based only on real history.

## 15. Promotion criteria

Mission Control cannot be called production-ready until:

- zero false-green DONE in chaos suite;
- stale/superseded work cannot block latest P0 indefinitely;
- every mutating run has one authoritative writer;
- every high-risk completion has independent verification;
- agent/provider replacement preserves TaskSpec and evidence;
- dashboard reconstructs current state without chat history;
- next task is deterministic from durable state;
- 24 h and 72 h soak pass;
- at least two execution backends/lanes pass the same conformance suite;
- human gates are explicit and minimal;
- paid fallback remains impossible without explicit human authorization.

## 16. Portfolio priority

Canonical execution order:

1. Generator Pism v1.0 — close current release.
2. Generator CV / LATAM Career OS — complete production implementation.
3. WORK ↔ ROS — revalidate and finish existing Cross-Repo Contract Convergence / bounded adapter.
4. UAOS — adopt durable execution/control-plane components and close execution-truth P0s.
5. Full BUILD-vs-ADOPT automation.
6. Lower-priority lanes.

This order is execution policy, not merely presentation.
