# LUKART Resource-Aware Agent Fabric (RAAF)

Date: 2026-10-05  
Status: PLANNING / P1 AFTER CURRENT P0 CLOSURE  
Authority: documentation_only

## Goal

Keep useful work flowing end-to-end without exhausting the user's workstation, without stale file locks, and without letting a dead/stalled agent hold work indefinitely.

The objective is **maximum useful throughput under resource and safety constraints**, not maximum process count.

## Core invariant

```
WORK_EXISTS + CAPACITY_EXISTS -> SOMETHING USEFUL RUNS
NO_SAFE_CAPACITY -> DEFER / REMOTE_ROUTE / LIGHT_WORK
DEAD_AGENT != OWNERSHIP
STALE_LOCK != BLOCKER_FOREVER
RUNNING != TRUE WITHOUT EXECUTION EVIDENCE
```

## 1. Agent roles

Roles are capabilities, not permanent vendor identities.

### SUPERVISOR / WATCHDOG
Read-only authority by default.
- validates PID/process fingerprint, heartbeat, lease, run_id and progress evidence;
- detects stale execution, repeated no-progress loops and resource pressure;
- never edits product code;
- can request recovery/requeue within policy.

### DISPATCHER
- classifies work by priority, resource envelope, risk and required capability;
- assigns executor/provider/worktree;
- performs work stealing across compatible queues;
- enforces WIP and RAM/concurrency budgets.

### BUILDER
- implements bounded product/code changes;
- owns exactly one isolated worktree/task attempt;
- cannot self-verify or self-promote.

### REPAIR / RECOVERY AGENT
- handles failed tests, broken environments, stale leases, worker bootstrap, dependency/tooling failures and bounded infrastructure repair;
- does not opportunistically expand product scope;
- has restart/repair budgets.

### VERIFIER
- independent family/provider where practical;
- read-only or isolated verification;
- validates exact candidate SHA and evidence.

### RESEARCH / SCOUT
- web/docs/repo discovery;
- produces evidence-backed candidates;
- never directly promotes technology.

### INTEGRATOR
- performs conflict resolution and landing preparation only after upstream attempts are complete;
- short-lived integration lease;
- exact-SHA rules.

## 2. Work classes

Each task gets a machine-readable `ResourceEnvelope`.

```
task_id
priority
risk_class
estimated_ram_mb
estimated_cpu_weight
io_weight
network_required
context_weight
expected_duration
mutates_repo
paths_or_domains
required_capabilities
privacy_class
cost_ceiling
deadline
```

Suggested classes:

- **T0 deterministic** — grep, schema check, hash, lint, small scripts.
- **T1 light AI** — classification, extraction, short summarization, routing, synthetic-data checks.
- **T2 normal engineering** — focused coding/test/review in one bounded module.
- **T3 heavy engineering** — cross-repo analysis, large refactor, long-context audit, migration.
- **T4 heavyweight/interactive** — ChatGPT Work or remote/cloud computer tasks requiring deep multi-step reasoning and large context.

## 3. Executor routing

### Local workstation
Best for:
- deterministic tools;
- Git operations;
- focused tests;
- light workers;
- one bounded builder when resource budget permits;
- local watchdog/reconciler.

### Live-verified zero-cost providers
Best for:
- T1;
- synthetic/public-data research;
- independent lightweight review;
- repeatability/benchmark lanes;
- overflow tasks that do not contain prohibited/private data.

Paid fallback remains blocked.

### Primary strong builder
Best for:
- T2/T3 implementation where quality dominates token cost/allowance.

### ChatGPT Work / cloud-computer lane
Best for:
- T3/T4;
- large repository audits;
- long-context design/reconciliation;
- complex multi-file migrations;
- heavy research and artifact production.

Until an automatable Work executor interface exists, the control plane can prepare a complete **Work Packet** but must mark the handoff `HUMAN_START_WORK` rather than pretending it launched Work automatically.

## 4. Resource governor

Never let the OS discover overload first.

Monitor:
- available physical RAM;
- committed memory;
- per-process working set;
- WSL/container memory;
- paging/page-fault pressure;
- CPU saturation;
- disk queue;
- active browser/cloud-computer sessions.

Pressure states:

```
GREEN  -> normal configured concurrency
YELLOW -> stop admitting new heavy local tasks
ORANGE -> checkpoint/pause preemptible low-priority workers; route new work remote/light
RED    -> preserve state, terminate only policy-approved disposable workers, run recovery only
```

Thresholds must be calibrated from telemetry rather than permanently hard-coded.

### Admission rule

Before spawn:
1. estimate task resource envelope;
2. compare with live free budget + reserved OS headroom;
3. reject local spawn if predicted pressure exceeds policy;
4. route to compatible remote/free/Work lane or select lighter queued work.

### Resource tokens

Use weighted semaphores, not "N agents":
- RAM tokens;
- CPU tokens;
- browser tokens;
- GPU tokens when applicable;
- provider quota tokens.

Example: two 500 MB workers may run while one 6 GB worker is deferred.

## 5. Work stealing without RAM thrash

Queues are capability/resource aware:

```
P0_REPAIR
P0_PRODUCT
P1_VERIFY
LIGHT_LOCAL
ZERO_COST_PUBLIC
HEAVY_REMOTE
RESEARCH
MAINTENANCE
```

When an executor becomes free:
1. take highest-priority compatible task;
2. if task cannot fit current resources, do not block queue head;
3. reserve it for an appropriate executor and steal the next compatible task;
4. preserve priority aging so light tasks cannot starve heavy work forever.

## 6. File/worktree ownership — eliminate pathological locks

### Rule: no long-lived product file lock

Builders mutate isolated Git worktrees. They should not hold shared repository files open as coordination locks.

### Lease, not permanent lock

Every mutable ownership claim contains:
- task_id;
- run_id;
- agent_id;
- worktree_id;
- path_scope;
- lease_id;
- fencing_token;
- acquired_at;
- heartbeat_at;
- expires_at.

Missing heartbeat + expired lease => ownership is reclaimable.

### Fencing token

A recovered task gets a newer monotonically increasing fencing token. Any stale worker presenting an older token is rejected at commit/integration/evidence write.

This converts a stale worker from "dangerous zombie" into "technically unable to finalize current work".

### Optimistic concurrency

At integration:
- compare exact base/head SHA;
- verify expected file hashes;
- rebase/merge in isolated integration worktree;
- conflict => explicit integration task, not indefinite lock.

## 7. Lock Reaper

Independent service; does not blindly delete locks.

For every lease/claim:
1. verify owner process identity, not PID alone;
2. verify fresh heartbeat;
3. verify task/run identity;
4. verify actual file/worktree activity/progress;
5. verify lease expiry;
6. classify:
   - LIVE;
   - IDLE_VALID;
   - STALE;
   - ORPHANED;
   - DEAD_OWNER;
   - AMBIGUOUS.
7. reclaim only deterministic STALE/ORPHANED/DEAD_OWNER cases.
8. AMBIGUOUS => quarantine + read-only reconciliation.

Every reclaim produces an evidence receipt.

## 8. No-progress watchdog

Heartbeat alone is insufficient.

Track:
- last meaningful tool call;
- last diff/hash change;
- test progress;
- log progress;
- artifact progress;
- provider response progress.

A process with fresh heartbeat but no meaningful progress crosses:
`WORKING -> SUSPECTED_STALL -> STALLED`.

Bounded recovery:
1. inspect;
2. one safe restart/resume;
3. alternate executor if compatible;
4. repair-agent task;
5. HUMAN_REQUIRED after configured failure budget.

No infinite restart loops.

## 9. Repair lane

Repair agents have a separate high-priority queue.

Examples:
- broken virtual environment;
- stale worktree metadata;
- lost worker heartbeat;
- malformed durable state;
- dependency resolution;
- CI bootstrap;
- provider adapter outage;
- recoverable lock/lease inconsistency.

Repair agent cannot:
- change product requirements;
- weaken tests;
- bypass exact-SHA;
- merge/promote;
- silently delete evidence.

## 10. Durable state

Mutable JSON files must not be the execution authority.

Initial durable backend:
- SQLite WAL;
- append/event-oriented execution ledger;
- transactional lease/fencing updates.

Scale-out option:
- PostgreSQL or another ACID database behind the same port.

JSON/Markdown/dashboard are projections only.

## 11. Queue truth

Task state is attempt-based:

```
QUEUED
LEASED
SPAWN_REQUESTED
PROCESS_VERIFIED
WORKING
SUSPECTED_STALL
STALLED
ARTIFACT_PRODUCED
VALIDATING
VALIDATED
COMMITTED
CI_VERIFIED
DONE

BLOCKED
QUARANTINED
FAILED
CANCELLED
UNCERTAIN
ORPHANED
```

No task can be RUNNING based only on scheduler intent.

## 12. Heavy-vs-light decision policy

A task is routed by:
- risk;
- context size;
- repo breadth;
- tool complexity;
- expected RAM;
- latency tolerance;
- privacy;
- provider cost/quota;
- required intelligence.

Example routing:

| Task | Preferred lane |
|---|---|
| hash/schema/grep | deterministic local |
| issue classification | Tev1/local/light provider after benchmark |
| public research extraction | VERIFIED_FREE |
| focused unit-test repair | normal builder |
| large cross-repo architecture audit | ChatGPT Work |
| multi-repo migration | Work / strong remote builder |
| independent exact-SHA review | different strong provider |
| stale lock diagnosis | repair agent |
| resource/heartbeat reconciliation | watchdog |

## 13. Provider Credential Broker

Agents should not receive raw long-lived keys in prompt/context.

The broker:
- stores secrets outside planner context;
- injects only when an approved adapter executes;
- records provider/key identity without logging the secret;
- supports rotation/revocation;
- applies provider/API/origin restrictions where available;
- enforces cost ceiling and paid-fallback policy;
- quarantines leaked/invalid credentials.

Google's migration to service-account-bound Gemini authorization keys reinforces this design; provider-specific credential formats remain adapter details.

## 14. End-to-end liveness SLOs

Measure:
- queue wait time;
- task start latency;
- useful-work ratio;
- stall detection latency;
- stale-lock recovery latency;
- restart success;
- RAM-pressure time;
- paging pressure;
- worktree conflict rate;
- tasks completed per hour/day;
- provider idle/quota loss;
- fraction of tasks with exact evidence.

"24/7" is validated by these metrics, not by process uptime alone.

## 15. Implementation order

Do not derail current P0.

1. close Generator Pism P0;
2. repair current UAOS durable-state/soak defect;
3. define ResourceEnvelope + resource telemetry;
4. implement transactional attempt ledger;
5. implement leases + fencing tokens;
6. implement Watchdog + Lock Reaper in read-only/shadow mode;
7. implement repair queue + bounded recovery budgets;
8. enable resource-aware admission/work stealing;
9. add zero-cost/light routing;
10. add Work Packet adapter for heavy lane;
11. run adversarial soak:
    - RAM pressure;
    - killed builder;
    - stale lock;
    - PID reuse;
    - corrupt projection;
    - provider outage;
    - simultaneous overlapping tasks;
    - uncertain external write.
12. promote only after exact-SHA independent review.

## 16. Key non-goals

- no "spawn everything" policy;
- no indefinite OS/file locks;
- no one agent acting as builder+watchdog+reviewer;
- no raw provider secrets in prompts;
- no paid fallback;
- no automatic merge/promotion;
- no claim of autonomous Work execution until an actual supported executor interface exists.

## 17. Cloud Burst Pool — heavy compute without local RAM pressure

The user's workstation must not be treated as the only heavy execution substrate.

Introduce a provider-neutral **CloudBurstPort** with ephemeral workers. A cloud burst worker is disposable compute; it is never an authority and never owns canonical state.

### Candidate lanes

#### Kaggle Notebooks — T4 x2
Current official Kaggle documentation/product announcements expose a **T4 x2** accelerator:
- 2 × NVIDIA T4;
- 16 GB VRAM per GPU;
- approximately 29 GB system RAM;
- notebook sessions are bounded (official docs describe up to 12 h execution for CPU/GPU sessions);
- free GPU availability is quota/queue constrained.

Best fit:
- GPU-heavy synthetic benchmarks;
- embeddings/reranking/model evaluation;
- local-model experimentation;
- media/model inference experiments;
- batch jobs that checkpoint frequently.

Not suitable as:
- permanent 24/7 scheduler;
- canonical task ledger;
- sole worker for an irreversible long-running operation.

#### Lightning AI free/start credits
Current public pricing advertises free starter GPU hours/credits, a free Studio and up to two concurrent GPUs on the free tier, with restart/session constraints.

Best fit:
- burst jobs requiring persistent-ish Studio ergonomics;
- GPU experimentation;
- temporary remote engineering worker.

Treat starter credits as ephemeral capacity, not durable 0-PLN infrastructure.

#### Google Colab free
Free GPU/TPU access exists, but GPU type, runtime lifetime and quotas are explicitly dynamic and not guaranteed.

Best fit:
- opportunistic experiments and overflow;
- never a hard dependency for P0 completion.

### Burst scheduling rules

1. provider must be live-verified at dispatch time;
2. job must have a checkpoint/restart contract;
3. no canonical state lives only on the ephemeral worker;
4. input bundle is content-addressed;
5. output/evidence bundle is pulled back and hash-verified;
6. worker can disappear without corrupting the task;
7. no real client/legal data goes to a cloud/free worker until privacy/terms/certification explicitly allow it;
8. no paid fallback/top-up;
9. if provider disappears, task returns to queue as DEFERRED/RETRY_ELIGIBLE rather than BLOCKED_FOREVER.

### Burst Worker Packet

```
task_id
run_id
exact_input_hashes
repo/ref/SHA
container/env manifest
resource envelope
checkpoint interval
expected outputs
validation command
cost ceiling = 0
privacy class
timeout
artifact return target
```

The worker returns a signed/content-addressed Execution Receipt. Results are untrusted until local/independent validation accepts them.

## 18. Human Authority Budget — stop signature spam

Human authority is scarce and must be spent at meaningful boundaries.

### Signature tiers

**Tier A — Autonomous checkpoint**
- agent/worktree checkpoint;
- no human interruption;
- may use a dedicated automation identity/key if approved;
- has provenance value only;
- cannot promote/merge/release.

**Tier B — Candidate freeze**
- one coherent bounded batch;
- validation passed;
- exact candidate SHA frozen;
- human signature may be requested here when policy requires it.

**Tier C — Promotion/release**
- separate high-authority approval/signature when required;
- cannot be inferred from Tier A or B.

### Consolidation rule

Do not ask the human to sign every small repair.

Accumulate causally related validated changes until:
- closure boundary;
- independent-review boundary;
- high-risk checkpoint;
- or branch/CI publication genuinely requires a signed identity.

Target:
`human_signing_events / independently_verified_closed_milestones` should trend toward 1 or below, never toward one signature per task.

### Automation signing identity

Long-term preferred model:
- a dedicated LUKART automation signing identity for low-authority checkpoint provenance;
- human personal key reserved for candidate/promotion boundaries;
- automation signature must be distinguishable from human authority in evidence;
- automation key cannot authorize merge/release merely because its signature is cryptographically valid.

This preserves provenance while avoiding a system that stops every few minutes waiting for the owner.

## 19. Sovereign Compute Mesh — federated multi-cloud execution

A fixed mapping such as "two permanent agents per project per cloud" is explicitly rejected. It wastes quota, increases idle RAM/process pressure and couples project throughput to provider topology.

Use a shared **Sovereign Compute Mesh (SCM)**.

### 19.1 Four independent compute domains

Initial 0-PLN / bounded-free candidate domains:

1. **MODEL CLOUD** — Ollama Cloud Free/starter pool; API/coding-agent inference, currently Free plan has one concurrent request.
2. **GPU BURST A** — Kaggle T4x2; batch GPU workloads, two 16 GB T4 GPUs, ephemeral.
3. **GPU/CPU BURST B** — Lightning AI free/starter credits and free CPU Studio; ephemeral and quota constrained.
4. **OVERFLOW BURST** — Colab Free; opportunistic GPU/TPU only, no guaranteed resources.

Additional orthogonal lanes:
- GitHub/Codespaces/Actions for CPU build/test where allowance permits;
- ChatGPT Work for heavyweight reasoning;
- Codex/Claude/Gemini/Hermes/Octop adapters;
- future verified-free providers.

These are **failure domains**, not authorities.

### 19.2 Project Virtual Cells

Each active project receives a logical cell, not dedicated hardware:

```
PROJECT CELL
├── PRIMARY EXECUTOR
├── INDEPENDENT VERIFIER / REPAIR
├── task queue
├── resource envelope
├── privacy/risk policy
├── exact-SHA/worktree bindings
└── evidence stream
```

Default concurrency target is two independent active roles per project **when capacity and task graph justify it**:
- one builder/executor;
- one verifier/repair/research role.

The dispatcher may temporarily allocate more or fewer workers.

### 19.3 Global worker pool

Workers are leased from pools:

```
STRONG_BUILDER_POOL
LIGHT_FREE_POOL
GPU_BURST_POOL
REPAIR_POOL
VERIFIER_POOL
RESEARCH_POOL
WORK_HEAVY_POOL
```

No provider is permanently assigned to one project.

Work stealing occurs across compatible projects after priority, privacy, capability and resource checks.

### 19.4 Anti-fragility

A project must continue when any one provider disappears.

Required:
- at least two certified executor routes for every critical capability;
- no canonical state held only by a provider;
- checkpoint/restart bundle for ephemeral workers;
- provider health and quota telemetry;
- automatic route decay when free quota or availability changes;
- no silent paid fallback;
- quarterly provider-extinction drills.

### 19.5 Two-agent rule is separation-of-duties, not process count

For material engineering work:
- Role A builds.
- Role B independently verifies, repairs infrastructure, or adversarially reviews.

Role B cannot simply be another session of the same process claiming independence. Where risk warrants it, use a different model/provider/runtime.

Two-agent semantics survive even when only one physical cloud request can run at once: roles can execute sequentially on different certified lanes while preserving independence.

### 19.6 Ollama Cloud placement

Ollama Free currently provides starter monthly usage and one concurrent request. Therefore it is **not** a two-agent parallel cloud by itself.

Use it as:
- one light/medium inference lane;
- overflow coding/review;
- Codex/OpenCode/Claude gateway candidate;
- model benchmark source.

Do not plan project throughput assuming unlimited/free parallelism.

### 19.7 Control plane

The SCM control plane remains lightweight and provider-neutral:
- transactional task/attempt ledger;
- leases/fencing;
- scheduler;
- resource/quota telemetry;
- Intent Provenance Firewall;
- Capability Passport;
- Credential Broker;
- receipts/reconciliation.

Heavy compute lives outside the control plane.

### 19.8 Universum scheduling objective

Optimize:

```
USEFUL_VALIDATED_PROGRESS
-----------------------------------------------
cost × risk × queue_delay × resource_pressure
```

Subject to hard constraints:
- correctness/evidence;
- authority;
- privacy;
- zero-paid-fallback policy;
- capability certification;
- blast-radius budget.

The objective is not agent count, GPU count or token volume.

### 19.9 Capacity target

Do not require four clouds to each run two agents permanently.

Target instead:
- 4 independent compute domains available;
- 2 independent logical roles per active priority project;
- enough global capacity for at least 4 concurrent useful lanes under normal conditions;
- graceful degradation to 1–2 lanes during provider/quota failures;
- queue remains live through work stealing.

Scale concurrency only after telemetry proves that higher concurrency increases closed validated milestones per hour.


