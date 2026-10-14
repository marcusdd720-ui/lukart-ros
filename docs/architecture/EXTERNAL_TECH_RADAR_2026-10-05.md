# External Technology Radar — 2026-10-05

Status: PLANNING / BUILD-vs-ADOPT INPUT / NON-AUTHORITATIVE

## Scope

Six user-selected YouTube materials were treated as discovery signals only. Conclusions below are based on the underlying projects, official documentation/repositories and current LUKART architecture constraints.

Videos:
1. https://www.youtube.com/watch?v=3w2TpHUfu94 — Hermes Obsidian Is CRAZY GOOD!
2. https://www.youtube.com/watch?v=ACTYK6Cnuos — Top Open-Source GitHub Projects: fmt, Tile Language, SkillSpector, QDuo, seiso & DroidDeck
3. https://www.youtube.com/watch?v=HzkljQI9T40 — 50 Use Cases with Tev1: A Tiny Local Decision Model (Ollama, $0)
4. https://www.youtube.com/watch?v=br_5gfgaA3I — OpenMuse Is an Open-Source AI Agent With Its Own Computer
5. https://www.youtube.com/watch?v=LYgV2wPU5DQ — I gave Claude Code a second brain so it builds mods for me
6. https://www.youtube.com/watch?v=qs8ocoZC4fw — Hermes Agent OS Just Changed AI Agents Forever!

## Executive decision

Two different winners exist:

- **Highest immediate implementation value:** NVIDIA SkillSpector.
- **Highest strategic architecture value:** OpenMuse durability/approval/runtime patterns.

Do not adopt any complete external agent OS as LUKART authority. Extract bounded capabilities behind LSAF contracts.

## Ranking

| Rank | Candidate | Decision | Why |
|---|---|---|---|
| 1 | NVIDIA SkillSpector | PILOT → ADOPT GATE | Directly addresses agent-skill/MCP supply-chain risk; static fail-closed scan, SARIF/JSON, CI-friendly, Apache-2.0. |
| 2 | OpenMuse runtime patterns | ADOPT PATTERNS / DO NOT FORK AS CORE | SQL leases, durable tasks, saved receipts, pause/resume/cancel, persistent browser, isolated computer, no hidden retry after uncertain writes. |
| 3 | seiso | SHADOW PILOT → SELECTIVE CI GATE | Attacks documentation drift and duplicate facts; especially relevant to architecture-heavy LUKART repos. |
| 4 | Claude Mods Brain / second-brain pattern | ADOPT KNOWLEDGE PATTERN | Provenance/date/version/drift tooling is useful; Obsidian remains a projection/UI, never authority. |
| 5 | Hermes Agent OS / Quicksilver | ADOPT EXECUTOR SEMANTICS | Persistent execution ledger, explicit UNKNOWN after interrupted runs, atomic job storage, profile isolation. Hermes stays replaceable executor. |
| 6 | Hermes + Obsidian | ADOPT AS VIEW/ADAPTER | Good human-readable knowledge surface; unsafe as shared multi-writer canonical memory. |
| 7 | Tev1 | BENCHMARKED PILOT | Useful local low-cost DecisionPort adapter for routing/triage. Accuracy is insufficient for authority/security/legal decisions. |
| 8 | TileLang | WATCH | Potential future inference/kernel optimization when LUKART owns suitable GPU/NPU workloads; premature now. |
| 9 | fmt | WATCH/LOW RELEVANCE | Mature library but only material if native C++ components become important. |
| 10 | QDuo | REJECT IMPLEMENTATION / UX IDEA ONLY | macOS-specific selected-text assistant; platform mismatch and little strategic leverage. |
| 11 | DroidDeck | REJECT | Gaming/SteamOS-on-Android scope is unrelated to current product/control-plane priorities. |

## Candidate analysis

### 1. SkillSpector

Primary source:
- https://github.com/NVIDIA/SkillSpector

Useful properties:
- static scanning without executing the candidate skill;
- prompt-injection, exfiltration, privilege escalation, supply-chain, memory-poisoning and MCP-focused checks;
- AST/taint/YARA/dependency scanning;
- JSON/Markdown/SARIF outputs;
- risk scoring and baselines;
- incomplete-analysis visibility.

LUKART adoption boundary:
- SkillSpector is one scanner inside a wider Capability Admission Gate, never the authority by itself.
- A clean scan does not mean a skill is trusted.
- A partial or failed scan must be fail-closed.
- Pin scanner version and candidate exact commit/SHA in evidence.

### 2. OpenMuse

Primary sources:
- https://github.com/CopilotKit/openmuse
- https://github.com/tahodev/openmuse

High-value patterns:
- durable server-owned jobs;
- SQL leases for interrupted-work recovery;
- persisted plans, approvals and receipts;
- explicit pause/resume/cancel/retry;
- persistent Chromium separate from an optional isolated Linux computer;
- no hidden retry after uncertain external writes;
- exact-action, one-time, expiring approvals in the security-focused implementation;
- hash-chained audit and signed checkpoints in the security-focused implementation;
- secrets kept outside planner context.

LUKART adoption boundary:
- Do not make CopilotKit Intelligence or OpenMuse a core dependency.
- Do not import a personal-agent product wholesale into ROS.
- Extract semantics into provider-neutral LSAF ports and deterministic acceptance tests.

### 3. seiso

Source:
- https://github.com/scarletkc/seiso

Value:
- one fact → one canonical home;
- document-kind conventions;
- diagnostics designed to be repairable by agents;
- stable rules vs preview rules;
- strong fit for docs-as-context repositories.

Adoption:
1. run non-blocking baseline;
2. classify current findings;
3. configure canonical fact ownership;
4. gate only stable/high-signal rules;
5. never let a linter rewrite architectural authority silently.

### 4. Claude Mods Brain / evidence-linked second brain

Source:
- https://agricidaniel.com/blog/claude-code-mods-guide

Useful pattern:
- plain Markdown portability;
- every material claim carries source/date/version;
- explicit audit tool before installing executable extensions;
- drift checker after upstream version changes;
- secretary/research agent cites notes instead of silently installing.

LUKART improvement:
- replace "second brain as truth" with Evidence-Gated Knowledge Projection.
- Canonical knowledge remains in typed/evented records; Markdown/Obsidian is a materialized human/agent view.

### 5–6. Hermes Agent OS + Obsidian

Primary docs:
- https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/note-taking/note-taking-obsidian

Adopt:
- one independent profile/state home per agent;
- jobs recorded before provider dispatch;
- immutable terminal attempt states including UNKNOWN;
- no automatic retry of abandoned/uncertain work;
- atomic job-file writes;
- skills compatible with an open skill format;
- Obsidian as filesystem-first Markdown UI.

Reject:
- multiple agents writing the same Hermes home/profile;
- one writable Obsidian vault as canonical shared memory;
- Hermes-specific state formats leaking into product/domain contracts.

### 7. Tev1

Sources:
- https://github.com/togethercomputer/tev1
- https://ollama.com/library/tev1

Use only behind a LUKART DecisionPort:
- classification;
- routing;
- low-risk triage;
- duplicate-idea candidate detection;
- log categorization;
- advisory sensitivity classification.

Never use alone for:
- legal conclusions;
- security authorization;
- promotion/merge decisions;
- destructive actions;
- financial/payment authority.

Confidence/logprobs are model preferences, not calibrated truth. Promotion requires a LUKART-labeled holdout benchmark.

## Biggest current LUKART weakness

The main weakness is **not model intelligence**.

It is the absence of one universally enforced, evidence-backed boundary that makes runtime truth, capability admission, side-effect authority and durable memory obey the same rules across every executor/provider/product.

The current UAOS soak failure is empirical evidence: control-plane state can claim progress while the execution substrate or persisted state has already failed.

### Failure class

```
CONTROL-PLANE INTENT
      !=
RUNTIME REALITY
      !=
DURABLE EVIDENCE
```

As the ecosystem adds providers, skills, plugins, memory systems and agents, this gap becomes a reliability and security multiplier.

## Proposed 15+ year architecture: LSAF Sovereign Trust Kernel

Introduce one narrow provider-neutral kernel between planning and all meaningful execution.

```
INTAKE
  ↓
CLASSIFY
  ↓
CAPABILITY ADMISSION
  ↓
EXECUTION LEASE + FENCING TOKEN
  ↓
EXACT-ACTION AUTHORIZATION
  ↓
EXECUTE
  ↓
EVIDENCE RECEIPT
  ↓
RECONCILE
  ↓
VALIDATE / PROMOTE
```

### A. Capability Passport

Every skill/plugin/provider adapter receives a machine-readable passport containing:
- capability_id + semantic version;
- upstream source + immutable commit/SHA;
- content hash;
- license/provenance;
- permissions manifest;
- network/domain allowlist;
- secrets required;
- SkillSpector/static scan report hash;
- dependency/SBOM evidence;
- benchmark result;
- compatible executors;
- certification status;
- expiry/revalidation date.

State:
`UNTRUSTED → QUARANTINED → SCANNED → BENCHMARKED → APPROVED → ACTIVE → DECAYED/REVOKED`.

No valid passport → no privileged execution.

### B. Durable Execution Ledger

Do not use mutable JSON files as execution truth.

Use a transactional append/event ledger (SQLite WAL initially; PostgreSQL when scale requires it):
- run/job/attempt IDs;
- lease owner;
- fencing token;
- PID/process fingerprint;
- heartbeat;
- state transition;
- exact-action hash;
- idempotency key;
- side-effect receipt;
- artifact/diff/commit/tree hashes;
- test and CI evidence.

JSON/Markdown/status dashboards become projections only.

### C. Fencing-token leases

A worker whose lease expires cannot commit state or artifacts after another worker takes ownership. This prevents zombie/stale workers from corrupting the current run.

### D. UNCERTAIN as first-class state

After a possibly completed external write with missing confirmation:
- never auto-retry;
- state becomes `UNCERTAIN`;
- reconcile/read back provider state;
- require human review for high-impact actions.

This unifies the strongest OpenMuse and Hermes semantics with LUKART Execution Truth.

### E. Exact-action capability tokens

Human/authority approval is bound to:
- one tool;
- exact arguments/hash;
- one capability passport;
- one run;
- one expiry;
- one use;
- explicit blast-radius budget.

The planner can propose but cannot mint authority.

### F. Evidence-Carrying Memory

A durable memory claim must carry:
- source/evidence references;
- source hash/version;
- valid_time;
- transaction_time;
- authority class;
- confidence only as advisory metadata;
- contradiction links;
- expiry/revalidation conditions.

Agents submit memory proposals. A memory authority validates/persists them.

Obsidian/Markdown becomes a generated projection, not the canonical store.

### G. Semantic Documentation Firewall

Combine:
- canonical machine-readable fact registry;
- seiso-style one-home rules;
- generated/referenced derived docs;
- drift CI;
- ownership metadata;
- source/version stamps.

A duplicated changing fact is treated as technical debt with a measurable drift risk.

### H. DecisionPort

Provide one typed interface for cheap/local decisions.

Resolution order:
1. deterministic rule/table if possible;
2. local decision model (e.g. Tev1) for low-risk advisory classification;
3. strong model;
4. heterogeneous verifier/quorum for high-risk tasks.

No model's probability is permission.

### I. Anti-Entropy Reconciler

Continuously compare:
- desired control-plane state;
- execution ledger;
- process/PID/heartbeat;
- lease/fencing token;
- Git branch/worktree;
- artifact hashes;
- CI state;
- external-provider receipts.

Mismatch cannot be reported as RUNNING/DONE. It becomes STALE, ORPHANED, UNCERTAIN or QUARANTINED with a repair plan.

### J. Vendor-extinction and drift tests

Quarterly:
- run the same certified capability through alternate executor/provider;
- simulate loss of Hermes/OpenAI/Claude/Obsidian/one cloud;
- replay golden tasks;
- verify no core data/authority is trapped in a vendor-specific surface.

Upstream changes to a skill/model/dependency automatically decay its certification until bounded revalidation passes.

## Pioneer-level extensions

1. **Evidence-Carrying Memory (ECM):** unsupported memory cannot silently become truth.
2. **Cryptographic Capability Passport:** executable capabilities carry provenance, scan, permission and benchmark evidence.
3. **Fencing-token Execution Truth:** stale workers become technically unable to finalize current work.
4. **Uncertainty-preserving side effects:** unknown outcome is retained instead of converted into retry/success.
5. **Automatic trust decay:** time/upstream changes revoke stale certifications.
6. **Blast-radius budgets:** maximum files/bytes/domains/cost/actions/time enforced outside the model.
7. **Bitemporal legal knowledge:** valid-time and transaction-time are mandatory for legal rules/facts, preventing old law/current-law confusion.
8. **Provider extinction drills:** portability is tested, not assumed.

## Implementation order

No new framework should derail current P0.

1. Close Generator Pism P0.
2. Repair UAOS execution state corruption and rerun real soak.
3. Pilot SkillSpector in shadow mode on LUKART skills/plugins.
4. Replace mutable task truth with durable attempt ledger + lease/fencing semantics.
5. Pilot seiso on documentation in report-only mode.
6. Introduce Capability Passport schema.
7. Introduce exact-action authorization and UNCERTAIN reconciliation.
8. Introduce Evidence-Carrying Memory + Obsidian projection.
9. Benchmark Tev1 behind DecisionPort.
10. Run provider/executor extinction drill.

## Promotion rule

This document records research and architecture direction only.

Nothing here authorizes:
- production deployment;
- main-branch merge;
- paid provider activation;
- weakening current exact-SHA or human promotion gates.

Every adoption remains subject to:
BUILD-vs-ADOPT → isolated branch/worktree → focused tests → regression → independent review → exact-SHA CI → explicit promotion gate.

## Additional input — 2026-10-05 evening

### Duplicate: Tev1 video

The supplied video `HzkljQI9T40` is the same Tev1 material already included in this radar. No duplicate backlog item is created. Existing disposition remains **BENCHMARKED PILOT / DecisionPort only**.

### Google AI Studio security upgrade

Video:
- https://www.youtube.com/watch?v=cjJbo3iv45Y
- title observed live: **Google AI Studio Just Got A Huge Security Upgrade**
- channel: Julian Goldie SEO

Official-source verification:
- Google is transitioning Gemini API access from standard keys to authorization keys;
- new AI Studio keys are authorization keys by default;
- auth keys are bound to a Google Cloud service account, enabling more granular identity/access control;
- auth keys are restricted to Gemini API by default and Google documents faster leaked-key enforcement;
- unrestricted standard keys are rejected and the documented 2026 migration deadline has passed;
- Google explicitly recommends keeping keys out of source control/client-side code, using backend/secret storage, restrictions, rotation and usage/billing monitoring.

LUKART decision: **ADOPT SECURITY PATTERN, NOT PROVIDER LOCK-IN**.

Required architecture consequence:
- add a provider-neutral **Provider Credential Broker**;
- raw long-lived credentials never enter planner/model context;
- credential lookup occurs only inside the approved provider adapter;
- record credential identity/version in evidence, never secret material;
- support per-provider restrictions, rotation, revocation and leak response;
- paid-fallback and cost ceilings remain enforced outside the model;
- Google Auth Key/service-account semantics are one adapter implementation, not a LUKART-wide credential format.

This materially reinforces IDEA-076/077 but does not require a separate provider-specific architecture.

# Batch 02 — six-video review (2026-10-05 late evening)

## Input videos

1. `RcN7hti2Lwo` — **Hermes Agent Just Got 500 FREE Plugins**
2. `xY4fqKU4tQA` — **How Hackers Trick AI Into Giving Up Secrets (Demos and free labs)**
3. `hz6-3-7GGyI` — **Agent AI w 2026 roku**
4. `57KdgMfSFfY` — **FREE Ollama API Key in 2 Minutes! (NO Credit Card Required)**
5. `fw1b7Lz5TE4` — **Tencent Octop (Open Source): ... OpenAI Dots & Muse**
6. `pxFDhIlhIac` — **The Cheapest Way To Run 100B+ Local Models**

YouTube remains discovery only. Material decisions below were checked against official repositories/docs or current provider pages.

## Executive ranking

### Best strategic system candidate: TencentCloud Octop — BUILD-vs-ADOPT PILOT

Why:
- MIT, self-hosted;
- multiple agents with independent workspaces/providers/cron;
- AgentTeams coordinator + members;
- document knowledge bases with citations;
- plugins + OAuth/MCP connectors;
- bidirectional ACP, including outbound delegation to OpenCode, Claude Code and Codex;
- browser, terminal and remote desktop;
- HTTP/SSE/WebSocket programmatic surfaces;
- SQLite WAL default / PostgreSQL optional;
- restart-safe reconstruction from control-plane DB.

Adoption decision:
- **do not replace LSAF/UAOS with Octop**;
- use Octop as a bounded executor/control-surface candidate and reference implementation;
- evaluate ACP delegation, workspace isolation, restart behavior, remote control and team orchestration through the LSAF conformance harness;
- reject Octop as authority/SSOT.

15+ year concern:
- current single-process architecture is simple and operationally attractive but is also a larger failure domain than the desired LSAF split control/execution planes;
- AgentTeams is beta;
- external model calls can still cost money and leave the host;
- its plugin/runtime trust model must not supersede LUKART Capability Admission;
- Octop lacks LUKART's required exact-SHA/evidence/promotion authority semantics.

### Best immediate security adoption: Arcanum + OWASP + PortSwigger security corpus/procedures

The David Bombal video points to:
- Arcanum Prompt Injection Taxonomy;
- Arcanum AI Security Resource Hub;
- authorized AI security labs/CTFs.

Official/current research adds:
- OWASP Secure Agent Playbook;
- PortSwigger Web LLM attack labs;
- SkillSpector from the previous batch.

Decision:
**ADOPT AS VERSIONED TEST INPUTS / PROCEDURES, NOT AS RUNTIME AUTHORITY.**

High-value facts:
- current Arcanum taxonomy exposes a machine-readable JSON corpus with intents, techniques, evasions and input surfaces;
- Arcanum's current repository describes 172 taxonomy nodes and is CC BY 4.0;
- its AI Security Resource Hub currently catalogs free/self-hostable labs, tools and references;
- OWASP Secure Agent Playbook provides structured procedures for agent-security audit, prompt-injection testing, MCP review, multi-agent threat modeling and AISVS/Agentic risk assessment;
- PortSwigger provides free interactive LLM attack labs, including indirect prompt injection and excessive-agency/API scenarios.

### Best plugin/ecosystem signal: Hermes Plugin Catalog — ADOPT ADMISSION PATTERNS, DO NOT BULK INSTALL

Live check of the official Hermes catalog JSON on 2026-10-05:
- entries: **448**, not literally 500 at the checkpoint;
- community: **439**;
- official: **9**.

Therefore the headline is rounded/marketing, while the ecosystem itself is real.

Strong upstream trust patterns worth adopting:
- exact 40-hex SHA pins;
- human-merged catalog admission;
- security scan on admission;
- removed/blocklisted plugin list;
- installed != enabled;
- capability declaration and re-consent on capability delta;
- non-interactive sessions fail closed for new capability grants;
- explicit provenance metadata.

Critical upstream warning:
- Hermes capability consent is **not a sandbox**;
- plugins execute as ordinary process/app code;
- cataloged != audited.

LUKART consequence:
**Hermes catalog becomes a discovery feed behind BUILD-vs-ADOPT + SkillSpector + Capability Passport, never an auto-install feed.**

High-value individual catalog candidates discovered:
- `hermes-review-loop` — unattended fixer/reviewer pattern, capped rounds, watchdog, never merges; PATTERN_ONLY first because it is Linux-only and has broad host/auth/webhook behavior;
- `hermes-security-audit` — Gitleaks + OSV-Scanner + Semgrep CE; isolated PILOT candidate;
- `github_app` — bot-first attribution and approval-gated GitHub writes; useful automation-identity pattern;
- `hermes-tailscale` — remote-control/connectivity pattern;
- official `snyk` plugin — possible security scanner adapter after overlap/cost analysis.

Do not adopt risky convenience plugins merely because they are cataloged.

### Best immediate zero-cost provider candidate: Ollama Cloud Free — LIVE TEST REQUIRED

Official Ollama state:
- Free plan is $0;
- it includes starter usage that refreshes monthly for a smaller set of starter models;
- local inference remains unlimited on owned hardware;
- cloud API/CLI is supported;
- API keys are supported for programmatic access;
- Ollama integrates with Codex, Claude Code, OpenCode and other coding tools;
- cloud requests require authentication;
- API keys currently do not automatically expire but can be revoked.

Classification:
`OFFICIAL_LIMITED_FREE / LIVE_ENDPOINT_NOT_YET_VERIFIED_FOR_LUKART`.

Do not label it VERIFIED_FREE until:
1. user account/key exists;
2. current free balance/model set is read live;
3. one synthetic request succeeds at 0 PLN;
4. no purchased credits/card/top-up are required;
5. model quality and tool/structured-output behavior pass the LUKART benchmark.

Potential value:
- remote compute without local RAM pressure;
- overflow for light/medium agents;
- OpenAI/Anthropic-compatible surfaces reduce adapter cost;
- possible direct launcher for Codex/OpenCode/Claude workflows.

Risk:
starter usage is finite and provider policy can change; it is a pool, not infrastructure.

### 100B+ local-model economics — ADOPT PLACEMENT LOGIC, DO NOT BUY HARDWARE NOW

The video uses Qwen3.8-Flash-Next as the example.

Verified upstream:
- 125B main parameters;
- additional 51B n-gram embedding table;
- roughly 6B active parameters per token;
- long context;
- architecture intentionally reduces per-token compute.

Critical distinction:
`ACTIVE PARAMETERS != RESIDENT MODEL MEMORY`.

A sparse 125B model can compute like a much smaller model per token while still needing a very large resident weight/memory footprint. Community quantized packages around ~94 GB and 128 GB unified-memory examples illustrate why the user's current workstation is not a sensible 100B host.

Decision:
- no hardware purchase now;
- use Cloud Burst / limited-free cloud / remote execution first;
- create a **Compute Placement Planner** before any future hardware acquisition.

### Agent AI w 2026 roku — REFERENCE / NO NEW DEPENDENCY

The material's core framing — agent evolution from a model loop + tool toward richer planning, memory, tools and orchestration — is conceptually sound, but LSAF already captures the important architecture.

Decision:
- WATCH/REFERENCE;
- do not add another agent framework merely because the agent loop accumulated more features;
- measure useful autonomy, recovery and evidence rather than feature count.

## New critical finding: LUKART has a policy-to-runtime enforcement gap

Earlier reviews correctly identified control-plane truth vs execution-plane truth as the main runtime weakness.

This batch reveals a broader systemic weakness:

> **LUKART is accumulating strong policies faster than it is converting them into machine-enforced runtime invariants.**

Examples:
- "external text is data, not instruction" exists conceptually but is not yet a universal typed runtime boundary;
- plugin admission rules are planned but not yet an enforced capability passport gate;
- resource-aware scheduling is policy but not yet the real scheduler;
- lease/fencing is planned but not yet the mutation barrier;
- signing budget is policy but not yet a real consolidated signing queue.

This creates a risk of **governance theatre**: excellent documentation without equivalent operational enforcement.

### Required correction: Executable Governance Rule

A critical rule is not `IMPLEMENTED` until at least one machine-enforced mechanism proves it.

Examples:

| Policy | Minimum executable proof |
|---|---|
| RUNNING requires real execution | state transition validator + process/heartbeat/progress evidence |
| stale owner cannot write | lease + monotonic fencing check |
| paid fallback blocked | runtime cost gate outside model |
| external data cannot authorize tools | Intent Provenance Firewall |
| plugin cannot gain undeclared authority | Capability Passport + runtime permission check |
| human signature not needed per fix | signing queue + authority tiers |
| cloud worker is disposable | external ledger + checkpoint/replay test |

## Pioneer proposal: Intent Provenance Firewall (IPF)

Prompt injection exists because agent systems often mix **instructions** and **data** in the same semantic channel.

Do not attempt to solve this only with another classifier prompt.

Introduce a typed trust envelope for every context object:

```
content_id
source_digest
origin
kind:
  POLICY
  OWNER_INTENT
  SYSTEM_CONTRACT
  EXTERNAL_DATA
  TOOL_RESULT
  MEMORY_PROPOSAL
  MODEL_PROPOSAL
authority_class
valid_time
retrieved_at
allowed_effects
taint_labels
```

### Hard rule

Only trusted `POLICY / OWNER_INTENT / SYSTEM_CONTRACT` can create or widen execution authority.

`EXTERNAL_DATA / TOOL_RESULT / MEMORY_PROPOSAL / MODEL_PROPOSAL` may inform reasoning but cannot authorize:
- tool execution;
- credential access;
- filesystem/network expansion;
- memory promotion;
- Git merge/release/signing;
- cross-case data access;
- policy modification.

### Intent Proof

Before every side-effecting tool call, require:

```
ACTION_REQUEST
  ↓
trusted owner/policy intent reference
  ↓
declared Capability Passport
  ↓
exact action/args hash
  ↓
blast-radius budget
  ↓
runtime authorization token
```

If the only causal source of an action is untrusted retrieved text, block it.

This is stronger than prompt filtering because it removes authority from poisoned data even when the model semantically follows it.

### Taint preservation

When external content is:
- summarized;
- translated;
- embedded;
- retrieved from RAG;
- copied into memory;
- passed between agents;

its untrusted provenance must travel with it. Transformation must not wash away trust labels.

## Pioneer proposal: Threat-Driven Corpus Compiler

Build an upstream-snapshot compiler:

```
Arcanum taxonomy
+ OWASP plays
+ PortSwigger/Lab metadata
+ internal incidents/regressions
        ↓
versioned attack vocabulary
        ↓
safe synthetic mutation/evasion generator
        ↓
surface matrix
        ↓
LUKART adversarial fixtures
```

Test every ingestion surface:
- webpages;
- PDFs/documents;
- emails;
- meeting transcripts;
- OCR;
- GitHub issues/PR/comments;
- RAG chunks;
- memory;
- MCP/tool descriptions;
- plugin manifests/README;
- code comments;
- agent-to-agent messages.

Expected invariants:
- no secret disclosure;
- no unauthorized tool call;
- no authority escalation;
- no cross-case leakage;
- no silent memory promotion;
- no cost-policy override;
- no merge/sign/release authority bypass.

## Pioneer proposal: Compute Placement Planner

Do not route models by parameter-count marketing.

Placement input:
- resident weights/bytes;
- active parameters;
- KV/context memory;
- memory bandwidth;
- CPU/GPU/NPU availability;
- predicted TTFT/tokens-per-second;
- concurrency;
- task risk/privacy;
- checkpointability;
- free quota/cost ceiling;
- provider health;
- required capability certification.

Output:
`LOCAL / LOCAL_LIGHT / CLOUD_FREE / CLOUD_BURST / STRONG_REMOTE / WORK / DEFER`.

### Hardware Acquisition Gate

Buying hardware is justified only when measured workload proves:
- sustained monthly compute demand;
- privacy/offline requirement;
- model quality benefit;
- acceptable amortized TCO;
- energy/thermal feasibility;
- benchmarked advantage over free/remote lanes.

This prevents spending thousands on hardware because a model headline says "125B local".

## Recommended implementation order after current P0

1. Generator Pism P0 closure.
2. UAOS execution-truth repair + real soak.
3. Minimal executable LSAF kernel:
   - transactional attempt ledger;
   - lease/fencing;
   - resource admission;
   - bounded repair;
   - evidence receipt.
4. Intent Provenance Firewall.
5. Agentic Security Certification Gate:
   - Arcanum snapshot;
   - OWASP playbook procedures;
   - SkillSpector/static scanning;
   - prompt-injection synthetic fixtures.
6. Hermes plugin-catalog discovery adapter in read-only mode.
7. Isolated BvA of `hermes-review-loop` patterns, not blind install.
8. Ollama Cloud Free live cost/endpoint benchmark.
9. Tencent Octop isolated conformance pilot.
10. Compute Placement Planner and Cloud Burst integration.
11. Only then consider hardware acquisition.

## Batch-02 promotion boundary

No production installation is authorized by this research report. The report authorizes only:
- backlog/manifest capture;
- bounded BUILD-vs-ADOPT research;
- synthetic/read-only tests;
- preparation of isolated pilots after higher P0 gates close.

### Ollama Cloud live-test checkpoint — 2026-10-05

Owner confirmed creation of an Ollama API key from the official settings page and named the worker context `UAOS-Zero-Cost-Worker-Ollama`.

Current state:
- official Ollama Free plan existence: VERIFIED;
- API key created by owner: OWNER_CONFIRMED;
- direct cloud API authentication: **PASS** on 2026-10-05 via authenticated `GET /api/tags`;
- cloud model catalog response: **PASS**;
- inference: NOT YET RUN;
- zero-cost runtime classification: NOT YET VERIFIED;
- paid fallback/top-up: BLOCKED.

Observed model names in the authenticated response included `gemma4:31b`, `kimi-k2.6`, `kimi-k2.7-code`, `deepseek-v4.1-flash`, `gpt-oss:120b`, `nemotron-3-nano:30b`, `nemotron-3-super`, `nemotron-3-ultra`, `glm-5.3`, `kimi-k3`, `glm-5.2`, `minimax-m2.7`, `glm-5.3-flash`, `deepseek-v4-pro:0813` and `gpt-oss:20b`. Presence in `/api/tags` proves catalog/auth visibility, not Free-plan entitlement for every listed model.

Next gate:
1. local secure capture of the key without posting it to chat or repository;
2. auth-only `GET https://ollama.com/api/tags`;
3. verify Free usage/balance and starter-model eligibility;
4. one synthetic inference request;
5. capture latency/token/evidence and confirm no purchased-credit consumption;
6. classify `VERIFIED_FREE`, `LIMITED_FREE`, or `BLOCKED`.

#### Account/usage evidence — 2026-10-05

Owner supplied live Ollama account screenshots showing:
- plan: **Free**;
- included/free cloud models explicitly listed: `gemma4:31b`, `gpt-oss:120b`, `gpt-oss:20b`, `nemotron-3-nano:30b`, `nemotron-3-super`, `nemotron-3-ultra`;
- Free usage meter: **0% used** at screenshot time;
- reset: **in 4 weeks**;
- purchased usage credits balance: **$0**;
- auto-reload: **Off**;
- billing: **no invoices yet**;
- account UI shows two earlier `gemma4:31b` requests at `<$0.01` each while included Free usage still displays 0% used.

Interpretation:
- zero-cost guardrails are favorable: no purchased balance and auto-reload is off;
- the listed starter models are explicitly eligible for included Free usage;
- prior requests are not treated as LUKART benchmark evidence because they predate this controlled test;
- one controlled synthetic inference request is still required before classifying the worker as inference-verified / zero-cost-verified.

#### Controlled Ollama inference attempt #1 — 2026-10-05

Model: `gpt-oss:20b` (explicitly listed by the account UI as included Free usage).

Observed result:
- HTTP/API generation completed: **PASS**;
- `done = true`;
- `total_duration = 2,097,195,736 ns` (~2.10 s);
- `prompt_eval_count = 78`;
- `eval_count = 16`;
- requested output assertion `LUKART_OLLAMA_PASS`: **NOT OBSERVED** because `response` was empty.

Interpretation:
- cloud inference path itself is live;
- this is not yet an application-output PASS;
- the test used `num_predict = 16`; `eval_count = 16` exactly, so the output budget was exhausted;
- `gpt-oss` is a thinking-capable model and Ollama's Generate API exposes thinking separately from response. A bounded retest with `think = false`, a slightly larger output cap, and `done_reason`/thinking diagnostics is required.
- zero-cost classification remains pending until the account Usage view is refreshed after the controlled inference and confirms included-Free consumption with purchased balance still `$0` and auto-reload Off.

State:
`INFERENCE_TRANSPORT_PASS / OUTPUT_ASSERTION_RETEST_REQUIRED / ZERO_COST_PENDING_USAGE_RECHECK`.

#### Controlled Ollama inference attempt #2 — 2026-10-05

Model: `gpt-oss:20b`.

Observed result:
- output assertion: **PASS** — exact final response `LUKART_OLLAMA_PASS`;
- `done = true`;
- `done_reason = stop`;
- `total_duration = 2,961,638,583 ns` (~2.96 s);
- `prompt_eval_count = 73`;
- `eval_count = 58`;
- reasoning/thinking text was still returned alongside the final response despite the request including `think = false`; treat this as provider/model behavior to benchmark separately rather than as a failure of the final-output assertion.

State:
`AUTH_VERIFIED / FREE_PLAN_VERIFIED / FREE_MODEL_ELIGIBILITY_VERIFIED / INFERENCE_VERIFIED / OUTPUT_ASSERTION_PASS / ZERO_COST_PENDING_USAGE_RECHECK`.

Remaining zero-cost gate:
Refresh Ollama Usage and verify that the controlled request consumed only included Free usage while purchased credits remain `$0`, auto-reload remains Off, and no invoice/paid balance appears.

#### Ollama Cloud zero-cost billing gate — PASS (2026-10-05)

Post-inference account screenshot confirms:
- `gpt-oss:20b` now shows **2 requests** in the monthly included-usage section;
- the two controlled requests appear under Recent requests;
- each request is shown as `<$0.01` accounting value;
- included Free usage display remains `0% used` (likely rounded at this tiny volume);
- purchased Usage credits balance remains **$0**;
- Auto-reload remains **Off**;
- no paid balance or invoice is present.

Classification:
`UAOS-Zero-Cost-Worker-Ollama = LIVE_VERIFIED_FREE_BOUNDED`.

Meaning:
- real authenticated cloud inference works;
- real included-Free accounting works;
- current out-of-pocket cost is 0 PLN / $0;
- this is **not unlimited**: it is bounded monthly included usage with current Free-plan concurrency limits and provider-policy dependency.

Certified-for-now scope:
- synthetic/public light-to-medium inference;
- zero-cost provider benchmarks;
- overflow/review/classification lanes after capability-specific benchmarks.

Not yet certified:
- client/legal private data;
- production legal reasoning;
- autonomous destructive/write authority;
- guaranteed 24/7 capacity;
- parallel two-agent execution on Ollama Free by itself.

#### Kaggle T4x2 live-test disposition — 2026-10-05

Live Kaggle notebook UI exposed `GPU T4 x2` and `TPU v5e-8` but both accelerators were disabled for the current account. Kaggle GPU access requires account/phone verification in this path.

Owner policy: **do not provide a phone number for this provider**.

Classification:
`KAGGLE_T4X2 = BLOCKED_BY_OWNER_PRIVACY_POLICY / DO_NOT_BYPASS`.

Consequence:
- do not attempt alternate-account, VPN, identity, phone-number or verification bypasses;
- keep Kaggle as WATCH-only until its access policy changes;
- replace it in the near-term Compute Mesh with providers whose free tier can be activated without this owner constraint.

Next preferred candidate: **GroqCloud Free**.
Official current evidence:
- Free Plan exists;
- signup/login supports Google, GitHub or email;
- payment method is required only when upgrading to Developer tier;
- Free Plan currently lists high-throughput limits including `openai/gpt-oss-120b` and `openai/gpt-oss-20b` at 30 RPM / 1,000 requests per day / 8K TPM / 200K tokens per day;
- exact account-specific limits must still be live-verified before certification.

#### GroqCloud Free — corrected consolidated live state (2026-10-05)

The earlier checkpoint in this report was incomplete. Prior controlled LUKART testing from 2026-10-04/05 already established:
- API key stored locally via Windows DPAPI;
- authenticated `GET /models`: HTTP 200;
- controlled inference: HTTP 200 on `qwen/qwen3.8-27b`;
- expected response `UAOS_GROQ_OK`: PASS;
- structured JSON: PASS;
- repeatability: 3/3 PASS;
- coding repair and Legal adversarial benchmark: PASS;
- synthetic ZUS hardened follow-up on `openai/gpt-oss-120b`: PASS;
- zero-cost lane classification: VERIFIED_FREE;
- observed response/account quota evidence included request limit ~1000 and token-per-minute limit ~8000 in the tested window.

Current official Free Plan baseline for `openai/gpt-oss-120b` and `openai/gpt-oss-20b` is 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD. Live response headers and exact account Limits are authoritative for remaining capacity and reset.

State:
`GROQ_FREE = LIVE_VERIFIED_FREE / LEX_READY_WITH_FRESHNESS_CHECK`.

Do not repeat account/key setup. Refresh live remaining/reset telemetry at dispatch time.
