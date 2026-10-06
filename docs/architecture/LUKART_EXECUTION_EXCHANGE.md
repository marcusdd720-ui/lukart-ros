# LUKART Execution Exchange (LEX) — Provider / Agent / Cloud Capacity Control Plane

Date: 2026-10-05
Status: PLANNING + PARTIAL LIVE CONTROL POLICY
Authority: documentation_only until runtime-enforced

## Purpose

LEX is the canonical routing layer that answers one question before every task:

> Which currently available execution route can deliver the earliest useful validated result, within privacy, authority, cost, quota and capability constraints?

Do not maintain one flat "provider list". Provider, model, agent, cloud, local runtime and project are different objects and must not be conflated.

## 1. Five-plane model

### A. Compute substrate
Where work physically runs:
- local Windows workstation;
- WSL Ubuntu;
- GitHub Actions;
- GitHub Codespaces;
- Kaggle / Colab / Lightning GPU burst;
- future remote CPU/GPU nodes;
- ChatGPT Work cloud computer where applicable.

### B. Inference provider
Who serves model inference:
- Ollama Cloud;
- GroqCloud;
- OpenRouter;
- Gemini / Google;
- Cloudflare Workers AI;
- APMix;
- future VERIFIED_FREE providers.

### C. Agent executor
Who performs multi-step work:
- Codex;
- ChatGPT Work;
- Hermes;
- Tencent Octop;
- Claude Code;
- OpenCode;
- Aider;
- Antigravity/other coding agents after verification.

### D. Model route
Specific model + provider + capability contract:
- provider;
- exact model ID;
- context;
- tool/JSON/code capabilities;
- quality benchmark;
- latency;
- quota/cost;
- certification state.

### E. Project cell
Consumer of capacity:
- LUKART WORK / Generator Pism;
- UAOS / LUKART ROS;
- Ogłoszenia PL / LUKART MEDIA;
- LATAM Career OS;
- future projects.

A dispatch route is a tuple:

```
ProjectTask
  -> AgentExecutor
  -> ModelRoute
  -> ComputeSubstrate
```

A component may omit a layer when not needed, e.g. deterministic local scripts do not need inference.

## 2. Static Capability Registry

Store durable facts only:
- component_id;
- type;
- vendor/project;
- capabilities;
- supported OS;
- privacy classes allowed;
- credential_ref (never secret);
- official evidence URLs;
- certification status;
- benchmark identity;
- known hard limits;
- lifecycle/deprecation data.

Static registry changes slowly.

## 3. Live Capacity Ledger

Store volatile state separately:
- status: UP / DEGRADED / RATE_LIMITED / QUOTA_EXHAUSTED / AUTH_FAILED / DOWN / UNKNOWN;
- last_probe_at;
- health TTL;
- queue depth;
- active leases;
- current concurrency;
- remaining requests/tokens/credits/minutes/core-hours;
- resource telemetry: free RAM/VRAM/CPU;
- provider/model availability;
- current latency and error rate;
- next known reset;
- reset confidence;
- source of observation.

Dynamic state is never copied into long-lived architecture text as if permanent.

## 4. Quota Window Model

Each route can have multiple simultaneous quota windows:

```
QuotaWindow
  metric: requests | tokens | neurons | minutes | core_hours | gpu_hours | credits
  limit
  remaining
  window: minute | hour | day | month | rolling | provider_defined
  reset_mode: fixed_utc | fixed_local | rolling | header_relative | dashboard_only | unknown
  next_reset_at
  observed_at
  source
  confidence
```

Examples:
- Groq: RPM/RPD/TPM/TPD; live response headers expose remaining request/token capacity and relative reset values.
- Cloudflare Workers AI: 10,000 free Neurons/day; reset 00:00 UTC.
- GitHub Actions: monthly minutes based on plan.
- GitHub Codespaces: monthly core-hours/storage based on plan.
- Ollama Free: monthly included usage; account dashboard is authoritative for account-specific balance/reset.

## 5. Freshness / TTL policy

A route cannot be selected from stale data when the stale field could change the decision.

Suggested maximum ages:
- local RAM/CPU/process state: 5–15 s;
- provider health: 60 s;
- per-request rate headers: current response / <=5 min;
- account quota dashboard/API: <=15 min before heavy dispatch, <=6 h for light dispatch;
- public plan/rate documentation: <=24 h;
- model catalog/deprecations: <=24 h;
- benchmark/certification: decays on model/provider/agent version change.

If stale:
`VERIFY_ON_DISPATCH`, not optimistic routing.

## 6. Quota reservation ledger

Do not let two agents independently believe the same remaining quota is available.

Before dispatch:
1. read authoritative/live remaining quota;
2. create a short-lived QuotaLease reservation;
3. subtract reserved capacity from schedulable headroom;
4. execute;
5. reconcile actual usage from response/account telemetry;
6. release unused reservation.

This prevents internal overbooking even when the provider only exposes coarse limits.

## 7. Reset Calendar

Maintain a normalized reset calendar:
- exact fixed reset timestamp where known;
- relative reset derived from response headers;
- rolling-window estimator;
- dashboard-only reset marker;
- UNKNOWN when provider semantics are not evidenced.

The scheduler should know both:
- `capacity_remaining_now`;
- `time_to_next_capacity`.

A task may wait for a near reset if that produces a faster or higher-quality validated result than immediate fallback.

## 8. Earliest Useful Completion (EUC)

Do not select the "nearest" agent by name, geography or provider order.

Calculate the earliest useful validated completion:

```
EUC = queue_wait
    + expected_start_delay
    + expected_runtime
    + expected_validation_time
    + reset_wait_if_needed
    + retry_risk_penalty
```

Hard filters are applied before scoring:
- cost policy;
- privacy;
- authority;
- required capability;
- certification;
- context size;
- compute/resource fit;
- provider terms;
- independent-review requirement.

Then rank eligible routes using:

```
Utility =
(priority_value * quality_score * success_probability * independence_bonus)
/
(1 + EUC + scarcity_penalty + failure_penalty + privacy_penalty)
```

No model score can override a hard policy gate.

## 9. Quota Shadow Price

"Free" quota is not economically free inside the scheduler because it is finite.

Assign a shadow scarcity price to each free pool based on:
- remaining percentage;
- time to reset;
- number/value of queued tasks;
- availability of substitutes;
- model uniqueness.

Use cheap/deterministic routes for trivial work and preserve scarce high-quality 120B/GPU capacity for tasks where it changes expected outcome.

This is an internal scheduling cost only; paid fallback remains blocked.

## 10. Separation-of-duties routing

For material tasks, LEX prefers:
- Builder on route A;
- Verifier on a genuinely independent route B.

Independence hierarchy:
1. different provider + different model family;
2. different provider + same model family;
3. same provider + different model;
4. same provider/model separate run (lowest independence).

Never count two sessions as independent merely because there are two processes.

## 11. Circuit breakers

Per provider/model/executor:
- consecutive auth errors -> AUTH_FAILED;
- repeated 429 -> RATE_LIMITED + reset/cooldown;
- repeated 5xx -> DEGRADED/DOWN;
- model 404/deprecation -> ROUTE_REVOKED;
- unexpected billing signal -> COST_QUARANTINE;
- tool/capability regression -> CAPABILITY_QUARANTINE.

Circuit breaker state is part of dispatch eligibility.

## 12. Provider/account reset semantics

Public docs describe baseline limits, but exact account limits win.

Examples as of 2026-10-05:

### GroqCloud Free — LIVE_VERIFIED_FREE
Prior controlled LUKART evidence:
- DPAPI-stored key;
- GET /models HTTP 200;
- inference HTTP 200;
- qwen/qwen3.8-27b response `UAOS_GROQ_OK`;
- structured JSON PASS;
- repeatability 3/3 PASS;
- coding repair and Legal adversarial PASS;
- hardened GPT-OSS 120B benchmark PASS;
- observed limit headers around request limit 1000 / token limit 8000 in the tested window.

Current official baseline for `openai/gpt-oss-120b` and `openai/gpt-oss-20b`:
- 30 RPM;
- 1,000 RPD;
- 8,000 TPM;
- 200,000 TPD.

Use live response headers to obtain remaining requests/tokens and relative reset. Exact account Limits page/API evidence overrides documentation.

### Ollama Cloud Free — LIVE_VERIFIED_FREE_BOUNDED
Controlled evidence:
- authenticated cloud catalog PASS;
- `gpt-oss:20b` inference PASS;
- post-request dashboard confirms included Free accounting;
- purchased balance $0;
- auto-reload Off;
- current Free plan supports one concurrent request;
- monthly included-usage reset is dashboard/account-defined.

### Cloudflare Workers AI Free — OFFICIAL_FREE_CANDIDATE
Current official baseline:
- 10,000 free Neurons/day;
- reset 00:00 UTC;
- excess requires Workers Paid;
- some frontier models explicitly require paid access despite the general free allocation.

Must pass account + synthetic 0-PLN live test before VERIFIED_FREE.

### GitHub Actions / Codespaces — ACCOUNT_PLAN_VERIFY
Current public allowances:
- GitHub Free Actions: 2,000 minutes/month; GitHub Pro: 3,000;
- Codespaces Free: 120 core-hours/month; Pro: 180.
Exact account plan, budgets and remaining usage must be read before scheduling. Set spending/budget policy to stop usage when included allowance is exhausted.

### Kaggle T4x2 — BLOCKED_PENDING_OWNER_VERIFICATION
GPU accelerator exposed in UI but unavailable without phone/account verification. Owner plans legitimate SIM verification later. Do not bypass.

### ChatGPT Work — HEAVY_REASONING / HUMAN_START_REQUIRED
Use for T3/T4 long-context/heavy tasks. Until a supported autonomous Work launch interface exists, LEX may prepare a Work Packet but cannot claim AUTO_DISPATCHED.

## 13. Project quota budgets

Global provider quota must not be consumed by one project accidentally.

Each project gets:
- daily/monthly soft allocation;
- P0 emergency reserve;
- max concurrent leases;
- allowed provider/privacy classes;
- borrowing rules.

Unused low-priority allocation can be work-stolen by higher-priority projects.

Reserve a configurable fraction of scarce capacity for:
- P0 repair;
- independent verification;
- deadline-critical work.

## 14. Dynamic route classes

```
READY_NOW
READY_AFTER_RESET
READY_AFTER_RESOURCE_RELEASE
READY_AFTER_HUMAN_START
DEGRADED
QUOTA_EXHAUSTED
RATE_LIMITED
AUTH_REQUIRED
BLOCKED_BY_POLICY
QUARANTINED
UNKNOWN
```

The dispatcher chooses the highest-utility `READY_NOW` route unless waiting for a near reset is provably better by EUC.

## 15. Runtime probes

Adapters should implement:

```
probe_health()
read_capabilities()
read_models()
read_quota()
read_reset()
read_cost_guard()
reserve_quota()
dispatch()
read_usage_receipt()
release_reservation()
```

Provider-specific details remain behind the adapter.

## 16. Evidence

Every dispatch receipt records:
- project/task/run IDs;
- selected route tuple;
- registry version/hash;
- quota snapshot before/after;
- reset prediction;
- resource snapshot;
- model/provider/agent versions;
- estimated vs actual runtime;
- tokens/requests/credits;
- cost classification;
- result/evidence hashes;
- fallback/circuit-breaker events.

This makes routing decisions replayable and auditable.

## 17. Failure rules

- UNKNOWN != AVAILABLE.
- Public plan != account entitlement.
- API key existence != capacity.
- Model listed != free entitlement.
- Free tier != unlimited.
- Provider UP != agent capability certified.
- Stale quota != schedulable quota for heavy work.
- Human-gated executor != autonomous worker.
- WSL/Ubuntu is a substrate/runtime, not an inference provider.
- GitHub Actions/Codespaces are compute lanes, not models.
- Codex/Hermes/Octop/Work are executors, not raw compute quotas.

## 18. Implementation path

Phase A — immediate:
1. canonical machine-readable registry;
2. Provider Capacity Sentinel refreshes public plan/model/deprecation/health data;
3. P0 Orchestrator reads registry before dispatch;
4. Groq adapter consumes live rate-limit headers;
5. Ollama adapter uses account usage evidence and one-concurrent-request reservation;
6. manual/unknown lanes fail closed.

Phase B:
1. quota reservation ledger in SQLite WAL;
2. reset calendar;
3. circuit breakers;
4. EUC scoring;
5. project quota budgets;
6. dashboard projection.

Phase C:
1. provider/model benchmark decay;
2. automated capability re-certification;
3. predictive quota forecasting;
4. provider-extinction drills;
5. adaptive shadow pricing.

## 19. Definition of Done

LEX is not IMPLEMENTED until:
- scheduler consumes machine-readable registry;
- at least two provider adapters expose live quota/reset data;
- quota reservations prevent overbooking;
- one provider outage/rate-limit causes automatic safe reroute;
- one reset event returns a route to READY;
- exact evidence explains why each route was selected;
- no paid fallback can occur;
- a stale registry entry cannot silently dispatch a heavy task.
