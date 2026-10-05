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
