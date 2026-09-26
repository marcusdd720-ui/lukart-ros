# LUKART ROS — Deferred Ideas Backlog

Status: non-authoritative parking lot for deferred ideas.
Canonical engineering standard remains `docs/WORKING_PRINCIPLES.md`.
Live implementation state remains GitHub `main` / active roadmap.
Items in this file are `PLANNED/DEFERRED` only and MUST NOT be treated as implemented, validated, certified, or release-authorized.

## IDEA-001 — Privacy-First Provider-Agnostic Preservation Fabric

Status: `DEFERRED`
Recorded: `2026-09-09`
Revisit not before: `2027-03-09`
Owner decision: do not use Amazon/AWS for real LUKART case data at this stage.

### Problem / motivation

Preserve case/replay artifacts outside the primary machine and GitHub without making any cloud provider a Product/CCL authority and without exposing plaintext case content to that provider.

### Target concept

- provider-independent storage contract under the existing `ArtifactEscrowBackendV1` / replay boundaries;
- mandatory client-side encryption before any sensitive bytes leave the trusted device;
- provider receives opaque ciphertext only; encryption keys remain outside provider storage and outside GitHub;
- no PII/case names/sygnatures in provider object keys or ordinary metadata;
- separate plaintext artifact identity and ciphertext object identity;
- at least one encrypted offline recovery copy on independent media;
- at least one external immutable/WORM provider with independently verifiable retention/version evidence;
- real restore/replay drill required before any `PRESERVED` claim;
- provider-specific evidence adapters remain replaceable and must not become a competing SSOT;
- future multi-provider mode may add a second independent European provider when risk, scale, SLA/RPO/RTO, client obligations, or cost justify it;
- AWS implementation already present in the repository may remain as dormant compatibility code, but Amazon is excluded from active real-data storage unless a future explicit business decision reverses that policy.

### Candidate provider direction for future review

Re-evaluate available European/privacy-aligned providers and no-cost/low-cost options at review time. Backblaze B2 was explored as a technically interesting S3-compatible WORM/Object-Lock candidate, but no provider is approved by this backlog entry and no account/storage deployment is authorized by it.

### Acceptance criteria for future activation

Before promotion from `DEFERRED` to an active stage, require fresh evidence on provider terms, jurisdiction/data handling, pricing, Object Lock/WORM semantics, version identity, API-verifiable retention, credential model, export/recovery path, portability, provider lock-in, deletion/retention controls, and client-side encryption/key-recovery design.

The future implementation should follow the canonical pipeline and fail closed. No plaintext case data may be uploaded during evaluation; synthetic artifacts must be used until the full privacy/security path is validated.

## IDEA-002 — Verified Legal Authority Fabric

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

The current engineering/trust substrate is materially more mature than the jurisdiction-specific legal-authority layer. A cryptographically correct replay can still preserve a legally wrong conclusion if the underlying statute, judgment, procedural rule, effective date, or holding is incorrect or stale.

### Target concept

Introduce a dedicated Legal Authority Fabric for immutable, source-bound snapshots of authoritative legal material, separate from case evidence and separate from the Canonical Case Ledger authority.

A legal authority record should bind, where applicable:

- jurisdiction;
- authority/source type;
- official source/provider identity;
- source reference and exact source bytes or verifiable snapshot identity;
- content digest;
- schema/parser identity;
- publication/decision date;
- effective-from/effective-until interval where applicable;
- retrieval/evaluation time;
- language;
- verification status;
- supersession/limitation relations.

Legal authority must remain an immutable input or deterministic/versioned projection. It MUST NOT become a second writable source of case history.

### Acceptance criteria for future activation

- material legal assertions can be traced to exact source identities;
- source tampering and source substitution fail closed;
- stale/unknown legal authority remains explicit;
- offline verification is possible for critical authority snapshots where technically feasible;
- no agent can manufacture an authority record without a verified source boundary;
- changes to authority bytes, parser/schema, effective period, or provider identity change the dependent result identity.

## IDEA-003 — Jurisdiction-Neutral Legal Core

Status: `DEFERRED`
Recorded: `2026-09-19`
Initial production jurisdiction: Poland + applicable European Union law.
Planned expansion direction: Colombia after approximately six months, subject to fresh legal/source validation and an explicit activation decision.

### Problem / motivation

Avoid encoding Polish procedural assumptions directly into the shared Product core and avoid building a second system for Colombia or later jurisdictions.

### Target concept

Keep the reusable core jurisdiction-neutral:

- Canonical Case Ledger;
- Evidence and private evidence boundary;
- epistemic state;
- Evidence Trust Graph;
- agent runtime and capability routing;
- reasoning;
- replay/provenance;
- security/authorization;
- rendering;
- external-action execution;
- validation and recovery.

Represent jurisdiction-specific behavior through explicit packages/contracts such as:

```text
jurisdictions/
    pl/
    eu/
    co/
```

Each jurisdiction package owns its legal sources, procedural rule packs, terminology, provider adapters, validation corpus and document-domain rules without gaining authority over the shared core.

### Acceptance criteria for future activation

- shared Product core has no hidden Poland-only legal assumptions at cross-jurisdiction boundaries;
- jurisdiction identity is explicit in persistent and cross-boundary legal artifacts;
- a Colombia package can be added without forking CCL, ETG, agent runtime, replay or security architecture;
- cross-jurisdiction matters preserve separate source/rule identities rather than translating one jurisdiction's law into another.

## IDEA-004 — Poland + EU First Production Legal Pack

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

LUKART needs a bounded first production legal vertical rather than broad claims of supporting all Polish law.

### Target concept

Use Poland as the first national jurisdiction and European Union law as an integrated supranational authority layer where applicable.

Initial source families may include, after independent source/API verification:

- Polish statutes and regulations from authoritative publication sources;
- KRS/PRS company-register data as case evidence where relevant;
- CEIDG/business-register data where relevant;
- Supreme Court / NSA / WSA case law from authoritative sources;
- EUR-Lex and CURIA/CJEU materials;
- official ZUS procedural and decision sources.

This backlog entry does not approve any specific endpoint until the endpoint, terms, schema, freshness semantics and evidence boundary have been freshly verified.

### Acceptance criteria for future activation

- every enabled source has a documented authority/non-authority contract;
- provider identity, schema, freshness and failure semantics are explicit;
- no ordinary web search is silently treated as equivalent to an official primary source;
- EU and Polish authority relationships remain explicit rather than flattened into one undifferentiated corpus.

## IDEA-005 — Citation Verification Gate

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

A valid citation string is not proof that an authority exists, that the cited text is correct, or that the authority supports the proposition attributed to it.

### Target concept

Create a fail-closed Citation Verification Gate between legal-authority ingestion and material legal output.

The gate should verify, where applicable:

- citation/sygnatura/ECLI identity;
- court/authority identity;
- decision/publication date;
- official source binding;
- quoted text or referenced section;
- proposition-to-source support;
- effective-law timing;
- supersession/limitation state;
- source and parser identities.

Statuses should include explicit states such as `VERIFIED`, `MISMATCH`, `STALE`, `UNVERIFIABLE`, and `MISSING_SOURCE`.

### Acceptance criteria for future activation

- an invented or mismatched case citation cannot pass;
- a real judgment with a falsely attributed holding cannot pass;
- a source change invalidates dependent verification;
- material legal drafting can require citation verification before `FILING_READY`;
- missing verification never becomes implicit PASS.

## IDEA-006 — Polish Procedural Rule Packs

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

A single generic legal agent cannot safely represent materially different Polish procedures, deadlines, authorities and remedies.

### Target concept

Extend the existing CIRP/rule-pack model with bounded, versioned, source-bound Polish procedural packs. Initial candidates include:

- `PL.ZUS.BENEFIT_APPEAL.*`;
- `PL.ZUS.CONTRIBUTION_DECISION.*`;
- `PL.ZUS.CONTRIBUTION_REMISSION.*`;
- `PL.ZUS.INSTALLMENT.*`;
- `PL.ZUS.ENFORCEMENT.*`;
- `PL.ADMIN.WSA.*`;
- `PL.COMPANY.KRS.*`;
- later bounded civil/KPC packs where justified.

Each executable rule should bind exact legal-source identities, effective dates, rule semantics, calendar/time assumptions and test evidence.

### Acceptance criteria for future activation

- unknown or stale rule-pack identity fails closed;
- deadlines are calculated only from verified rule semantics and verified/provisional trigger evidence;
- a rule outside its effective period cannot silently execute;
- each rule pack has focused, adversarial and regression coverage;
- procedure-specific logic does not leak into the shared jurisdiction-neutral core.

## IDEA-007 — Replaceable External Provider Adapter Architecture

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

A monolithic `GovAPIsIntegrator` would combine unrelated trust boundaries, schemas, authentication models, privacy classes, freshness requirements and failure semantics.

### Target concept

Use small provider-specific adapters behind common contracts, for example:

```text
core/external_sources/
    contracts.py
    registry.py
    freshness.py
    transport.py
    pl/
        krs_open_api.py
        ceidg_adapter.py
        zus_public_source.py
    eu/
        eurlex_adapter.py
        curia_adapter.py
```

Each adapter should declare:

- provider identity/version;
- allowed hosts/endpoints;
- operation/read semantics;
- input/output schema;
- timeout/retry policy;
- freshness policy;
- authentication class;
- privacy classification;
- provenance/evidence output;
- explicit failure states.

No adapter may silently substitute ordinary public search for a failed authoritative provider.

### Acceptance criteria for future activation

- provider failure returns an explicit non-PASS state;
- redirects or host substitution outside allowlist fail closed;
- malformed/truncated/unknown-schema responses fail closed;
- retry is bounded and only permitted for explicitly safe operations;
- replacing a provider does not change the Product authority model.

## IDEA-008 — Colombia Jurisdiction Pack

Status: `DEFERRED`
Recorded: `2026-09-19`
Target direction: evaluate activation approximately six months after the Poland + EU vertical reaches a sufficiently stable production state.

### Problem / motivation

Prepare for expansion into Colombia without copying Polish legal semantics or creating a separate Product architecture.

### Target concept

Build Colombia as another jurisdiction package over the same shared core:

- Colombian official legal-authority sources;
- Colombian procedural rule packs;
- Colombian provider adapters;
- Spanish legal terminology and rendering rules;
- Colombian validation/Gold corpus built from approved synthetic/anonymized materials;
- explicit handling of cross-border PL/EU/CO matters.

Candidate public institutions and source families must be researched afresh at activation time. No Colombian provider/API is approved merely by being named in earlier design discussions.

### Acceptance criteria for future activation

- fresh review of Colombian authoritative sources, procedure, privacy/data-transfer constraints and provider/API terms;
- Colombia package uses the same CCL/evidence/epistemic/replay/security invariants as Poland;
- no Polish deadline, remedy, court, terminology or authority assumption is inherited without an explicit Colombian rule/source;
- Spanish output is domain-reviewed before any production claim;
- cross-border conflicts remain explicit `UNKNOWN/UNRESOLVED` until governed by verified rules.

## IDEA-009 — Legal Domain Maturity Program

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

Current strategic gap identified during the 15+ year review:

`Assurance maturity > Legal-domain maturity`.

The project already contains substantial engineering controls for identity, provenance, replay, privacy, authorization, recovery and fail-closed validation. The next material gains should increasingly measure and improve legal correctness rather than add assurance complexity without a demonstrated gap.

### Target concept

Create a measured legal-domain maturity program covering:

- source coverage;
- authority freshness;
- citation precision;
- proposition-to-authority support;
- procedural-rule correctness;
- deadline correctness;
- filing-route correctness;
- abstention quality;
- contradiction detection;
- regression against independently reviewed legal Gold sets.

The program must remain separate from engineering CI success. Engineering PASS does not certify legal correctness.

### Acceptance criteria for future activation

- explicit legal-domain metrics and error taxonomy;
- independently reviewed legal Gold/evaluation material where required;
- no self-certification by the same agent/model that generated the answer;
- changes to legal evaluators/corpora receive independent identity and versioning;
- measured improvement is required before promotion of new legal capabilities.

## IDEA-010 — Controlled Legal Agent Layer

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

Adding many unconstrained specialist personas would enlarge the authority and hallucination surface without proving a need.

### Target concept

Prefer a small number of bounded agents that reuse the existing capability router, contracts and validation gates. Initial candidate roles:

1. `LegalAuthoritySynthesisAgent` — consumes verified authority snapshots and produces a typed synthesis artifact;
2. `CitationVerificationAgent` or deterministic gate — verifies source/citation/proposition binding without case-history write authority;
3. `FilingRedTeamAgent` — challenges a proposed filing for unsupported assertions, stale law, standing, deadline, recipient/route, remedy competence, missing attachments and privacy disclosure.

Agents should not:

- directly write Evidence Trust Graph state;
- bypass Canonical Case Ledger authority;
- treat model memory as verified law;
- hide `UNKNOWN/UNRESOLVED`;
- declare external actions completed without receipt evidence.

### Acceptance criteria for future activation

- capability routing is schema/certification based, not keyword-only routing;
- each agent has explicit inputs, outputs, permissions and budgets;
- no agent gains broad network/filesystem/write access solely for convenience;
- adversarial tests cover fabricated citations, stale authority, cross-case substitution and unsupported legal conclusions;
- agent output remains untrusted until normal Product validation accepts it.

## IDEA-011 — Persistent Agent Work Ledger

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
External inspiration: `planning-with-files`; no external repository is approved by this entry.

### Problem / motivation

Long-running LUKART engineering tasks can waste high-capability agent context and repeated GitHub reads after compaction, restart or transfer between Chat, Work, Codex or another approved execution surface. Reconstructing the plan, decisions, exact SHA, tests and remaining steps from conversation history is inefficient and can create state drift.

### Target concept

Create a LUKART-native, content-addressed resumable task-state contract containing: task/stage identity, objective, last verified `main` SHA, active branch/PR/candidate SHA, ordered plan, research/decisions, execution log, test evidence, blockers, next executable action, state digest/version and last verification time.

The useful `plan / findings / progress` separation may be borrowed conceptually, but the ledger remains Factory-only. It MUST NOT become a second roadmap, case-history authority, Canonical Case Ledger, evidence store or substitute for live GitHub state.

### Resource-efficiency objective

A fresh agent session should recover the active task from one small persisted state plus bounded live-state verification instead of re-reading large chats and repeatedly traversing GitHub.

### Acceptance criteria

- cold-session recovery does not depend on model memory;
- stale state is detected when live `main`, PR head, candidate SHA or required evidence changes;
- unfinished required steps cannot be represented as closed;
- task-state identity is tamper-evident;
- private case data never enters public task-state files;
- live GitHub remains authoritative for current SHA/PR/CI state.

## IDEA-012 — Resource-Aware Hybrid Agent Budget Controller

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
External inspiration: OmniRouter-style fallback ideas; OmniRouter itself is not approved.

### Problem / motivation

Astra/Work-class execution is scarce. LUKART already has `AgentResourceLimits.max_model_calls` and `max_cost_units`, but the current gate mainly validates reported usage after execution. A pre-execution budget/reservation and escalation layer is still missing.

### Target concept

Extend the existing LUKART `CapabilityRouter` rather than replacing it:

1. `LOCAL_DETERMINISTIC` — repository inspection, hashing, schemas, tests, static analysis, replay;
2. `LOCAL_OR_LOW_COST_MODEL` — only capabilities separately validated for that model;
3. `HIGH_CAPABILITY_MODEL` — difficult synthesis/reasoning;
4. `ASTRA_WORK_ESCALATION` — only when complexity or computer-use justifies the scarce Work pool.

Add pre-run budget reservation, per-task/stage ceilings, provider/model/version identity, explicit escalation reason, circuit breaker, approved fallback sets and local/deterministic preference.

### Critical boundary

This cannot increase or bypass ChatGPT Work/Codex limits. Its purpose is to reduce consumption by moving suitable work to deterministic/local or separately approved lower-cost execution paths.

### Acceptance criteria

- current capability/certification/schema routing remains authoritative;
- no provider/model is selected merely because it is free;
- trust-sensitive fallbacks require explicit approval;
- insufficient reserved budget fails closed before expensive execution;
- execution evidence records actual model/provider/version and measured resource use.

## IDEA-013 — Local-First GitHub Evidence Cache and Bounded Remote Access

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Repeated remote reads of unchanged files, commits, PR metadata and workflow state consume GitHub/API/tool capacity and agent context.

### Target concept

Use the exact-SHA local clone/worktree as the primary inspection surface for code search, diffs, history, tests and static analysis. Synchronize from GitHub only at explicit trust boundaries. Key cache entries to immutable commit SHA and record `verified_at`, repo and ref.

Remote GitHub authority remains mandatory at stage start, candidate publication, CI verification, guarded merge and post-merge closure.

### Acceptance criteria

- local inspection/testing proceeds without repeated GitHub reads for the same exact SHA;
- current PR/CI/merge claims always require remote verification;
- cache entries cannot silently follow a moving branch;
- stale/unknown cache fails closed at promotion/closure gates;
- measured remote-call reduction does not weaken exact-SHA evidence.

## IDEA-014 — Self-Hosted / Local Validation Offload

Status: `DEFERRED / RESEARCH CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Deterministic lint, type-check, unit/regression and architecture checks can be wastefully repeated on hosted runners when equivalent preflight can be proven locally.

### Target concept

Evaluate a controlled hybrid topology: local deterministic preflight first; hardened self-hosted WSL/Linux runner for selected trusted workflows; GitHub-hosted execution retained where independent environment properties are useful or required.

### Acceptance criteria

- explicit threat model for self-hosted execution;
- untrusted PR/fork code cannot reach privileged host secrets/resources;
- exact checked-out SHA and runner provenance are recorded;
- local/self-hosted PASS never masquerades as independent external validation;
- broad adoption requires measured reduction in unnecessary hosted runs.

## IDEA-015 — Read-Only External Research Ingestion Adapter

Status: `DEFERRED / RESEARCH-ONLY`
Recorded: `2026-09-26`
External inspiration: Agent Reach-style multi-source access.

### Problem / motivation

Reusable read-only ingestion of public GitHub, RSS, web and YouTube transcript material could reduce expensive interactive research time before high-capability synthesis.

### Target concept

Evaluate replaceable read-only adapters for non-authoritative public research. Retrieved material remains untrusted input and MUST NOT become legal authority, case evidence, verified fact or trusted instruction merely because an adapter fetched it.

### Acceptance criteria

- read-only capability by default;
- source/provider identity and retrieval time recorded;
- credentials/cookies remain outside repository/case artifacts;
- prompt injection is treated as data, never instruction;
- legal-authority workflows still require the Verified Legal Authority Fabric.

## IDEA-016 — Vendor-Neutral Memory Provider Fabric

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
External inspiration: Hermes memory providers, Honcho and OpenClaw-style persistent memory.

### Problem / motivation

Long-running agent work benefits from cross-session recall, but memory must not become an unverified truth authority. LUKART needs continuity without allowing remembered statements to override live GitHub state, Canonical Case Ledger, evidence, legal authority or current validation evidence.

### Target concept

Introduce a vendor-neutral `MemoryProviderV1` sidecar contract for contextual agent continuity. Candidate backends may include Honcho-like systems, Hermes built-in memory, Mem0/Hindsight-style providers or a local implementation, but none is trusted by default.

Memory may contain:

- prior workflow decisions;
- user/project preferences;
- prior experiments and rejected approaches;
- task continuity summaries;
- useful recurring project context;
- pointers to authoritative artifacts.

Memory MUST NOT independently establish:

- case facts/evidence;
- legal authority;
- current GitHub/CI/PR state;
- certification status;
- release authorization;
- Canonical Case Ledger state.

### Acceptance criteria

- every recalled memory carries provider identity, timestamp and source/provenance where available;
- recalled memory is explicitly marked contextual/untrusted until revalidated when it affects a trust-sensitive decision;
- provider replacement does not change Product authority;
- memory export/import is possible without vendor lock-in;
- private/sensitive memory storage follows the private-case security boundary;
- no memory backend can bypass normal validation gates.

## IDEA-017 — Controlled Knowledge Consolidation / Dreaming

Status: `DEFERRED / RESEARCH CANDIDATE`
Recorded: `2026-09-26`
External inspiration: OpenClaw-style background memory consolidation.

### Problem / motivation

Raw session history grows quickly and makes retrieval noisy and expensive. Useful repeated knowledge should be distilled, but autonomous promotion of remembered statements to trusted knowledge would create a hidden second authority.

### Target concept

Evaluate a staged consolidation pipeline:

```text
raw events / conversations
        ↓
candidate insight
        ↓
repetition / usefulness / evidence scoring
        ↓
knowledge candidate
        ↓
validation / human or deterministic gate
        ↓
durable project knowledge
```

The process may run in background-like phases, but LUKART should use explicit states rather than anthropomorphic trust semantics.

### Acceptance criteria

- consolidation cannot promote unverified case/legal claims into trusted state;
- source links remain available after summarization;
- contradictory candidates remain explicit rather than silently merged;
- promoted knowledge has version/digest/provenance;
- stale knowledge can be invalidated by newer authoritative evidence;
- measurable retrieval/context reduction is demonstrated.

## IDEA-018 — Fast Task Classifier Before Expensive Models

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
External inspiration: JEV-style classifier/dispatcher.

### Problem / motivation

Using a high-capability model merely to decide which model/tool should execute a task wastes scarce Work/Codex capacity.

### Target concept

Add a small, bounded classifier before the existing capability router. It should classify task requirements such as:

- deterministic/local;
- low-cost model;
- standard high-capability model;
- Astra/Work escalation;
- research-only;
- reviewer/adversarial path.

The classifier outputs only a structured route recommendation and confidence/evidence fields. It does not execute the task or make trust-sensitive conclusions.

### Acceptance criteria

- classifier failure or low confidence falls back to a safe deterministic policy;
- model/provider choice remains constrained by approved capability/certification rules;
- classification output is schema-bound and auditable;
- routing accuracy and resource savings are measured against a baseline;
- classifier cannot silently downgrade a task that policy requires to run on a stronger/approved executor.

## IDEA-019 — Multi-Agent Worktree Orchestrator

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
External inspiration: parallel Codex/agent workflows.

### Problem / motivation

Parallel agents can shorten large engineering tasks, but uncontrolled parallel edits create merge conflicts, duplicated work and authority ambiguity.

### Target concept

Use isolated branches/worktrees and explicit agent roles under one orchestrator:

- builder;
- focused-test agent;
- adversarial reviewer;
- security/policy reviewer;
- research agent;
- synthesis/landing coordinator.

Each parallel job binds: input SHA, scope, permissions, budget, expected artifact and allowed files/operations.

### Acceptance criteria

- no two agents mutate the same authority surface without explicit coordination;
- every result binds to its input SHA and isolated worktree/branch;
- agent outputs are compared/reviewed before candidate promotion;
- parallelism never bypasses exact-SHA CI or independent-review boundaries;
- failed/abandoned worktrees can be safely discarded;
- measured wall-clock benefit justifies orchestration complexity.

## IDEA-020 — Controlled Self-Improvement Loop

Status: `DEFERRED / RESEARCH CANDIDATE`
Recorded: `2026-09-26`
External inspiration: RSI/self-improving agent patterns and Hermes review loops.

### Problem / motivation

Agents can propose improvements to prompts, routing, heuristics, skills or parameters, but allowing the same agent to change and certify its own behavior would violate LUKART validation principles.

### Target concept

Use an explicit lifecycle:

```text
Observation
→ Hypothesis
→ Candidate Improvement
→ Shadow Mode
→ Experiment
→ Measurement
→ Independent/Separate Validation
→ Promotion or Rejection
```

No self-generated improvement becomes production behavior solely because the proposing agent reports better performance.

### Acceptance criteria

- baseline and candidate are evaluated on fixed/versioned evidence;
- improvement criteria are defined before promotion;
- proposer and validator are separated where material;
- regressions/adversarial cases are included;
- rollback is deterministic;
- self-improvement cannot alter governance, trust or security policy without explicit authorization.

## IDEA-021 — Local Model Execution Tier

Status: `DEFERRED / HIGH-VALUE RESEARCH CANDIDATE`
Recorded: `2026-09-26`
External inspiration: current local-model workflows on consumer GPUs.

### Problem / motivation

A meaningful share of preprocessing and low-risk engineering work may not require remote high-capability models. Running suitable workloads locally can reduce Work/API usage, improve privacy and remove network/rate-limit dependence.

### Candidate workloads

- document classification;
- PII detection/redaction assistance;
- keyword/entity extraction;
- text normalization;
- simple summarization;
- embeddings/reranking;
- synthetic-data assistance;
- test-case generation;
- repository/file classification;
- low-risk drafting where quality has been separately benchmarked.

Trust-sensitive legal reasoning, architecture and difficult debugging remain on approved higher-capability paths unless a local model is separately validated for that capability.

### Acceptance criteria

- benchmark on representative LUKART/Synthetic Test Data Factory tasks;
- explicit hardware/runtime requirements and latency measurements;
- no capability is promoted based only on anecdotal quality;
- local model/version/quantization identity is recorded;
- privacy-sensitive local processing remains within approved device boundaries;
- fallback/escalation rules are deterministic and auditable.

## IDEA-022 — LUKART Agent Runtime as the Control Plane

Status: `DEFERRED / STRATEGIC HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

LUKART should not become a clone of Hermes, OpenClaw, Codex, ChatGPT Work or any single model/provider. Those systems can evolve, disappear, change pricing, change limits or be replaced. LUKART therefore needs its own stable control plane above interchangeable executors.

### Target concept

Build a `LUKART Agent Runtime` in which external and local agent/model systems are execution backends rather than Product authorities.

Candidate executor classes:

- Hermes;
- Codex;
- ChatGPT Work;
- GPT-6 Sol / Astra-class models;
- approved Claude/Gemini-class providers where justified;
- local Qwen/Llama-family models;
- Ollama / llama.cpp / vLLM-backed local endpoints;
- future compatible executors.

LUKART remains responsible for:

- governance;
- capability routing;
- evidence/provenance;
- validation and fail-closed gates;
- exact-SHA execution identity;
- memory-provider contracts;
- resource budgets;
- authorization;
- task-state continuity;
- promotion/closure decisions.

No executor gains authority merely because it is more capable, cheaper, local or available.

### Architectural boundary

```text
LUKART
├── governance
├── routing
├── evidence
├── validation
├── memory contracts
├── task ledger
└── resource budgets
        │
        ▼
EXECUTOR ADAPTERS
├── Hermes
├── Codex
├── ChatGPT Work
├── Sol / Astra
├── local model endpoint
└── future providers
```

### Acceptance criteria

- provider/model replacement does not alter Product authority;
- every executor has an explicit capability/schema/permission/budget contract;
- executor/model/version identity is recorded in result evidence;
- no backend can bypass CCL, legal-authority, validation or release gates;
- failover is explicit and policy-bound, never silent;
- trust-sensitive capability changes invalidate prior certification unless explicitly covered.

## IDEA-023 — Local-First 24x7 Agent Execution Fabric

Status: `DEFERRED / HIGH-VALUE RESEARCH CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Continuous agent operation does not require every task to consume scarce Work/Astra capacity. Many collection, preprocessing, monitoring, classification, local validation and routine execution tasks can run continuously on owned infrastructure.

### Target concept

Create a layered local-first runtime:

```text
scheduler / events
       ↓
fast task classifier
       ↓
local deterministic tools
       ↓
local model endpoint
       ↓
approved remote model escalation
       ↓
Astra/Work only when justified
```

Supporting components may include:

- local model serving through Ollama/llama.cpp initially and vLLM where scale/throughput justify it;
- scheduler/routines;
- read-only research collectors;
- inter-agent messaging;
- isolated worktrees;
- persistent task ledger;
- memory-provider sidecar;
- operator dashboard;
- health checks, audit logs and kill switch.

### Resource objective

Use local compute for repeatable low-risk tasks and reserve scarce remote/high-capability execution for difficult reasoning, architecture, legal synthesis, complex debugging and other explicitly classified workloads.

### Acceptance criteria

- no 24x7 agent obtains unrestricted filesystem/network/secrets access by default;
- continuous execution has explicit budgets and circuit breakers;
- local runtime can operate without GitHub polling except at required trust boundaries;
- remote escalation is auditable and policy constrained;
- local/background operation cannot self-promote code, rules, memory or legal conclusions into trusted state;
- operational metrics demonstrate reduced Work/API usage before broad activation.

## IDEA-024 — Bot/Profile Runtime with Isolated Memory and Toolsets

Status: `DEFERRED / RESEARCH CANDIDATE`
Recorded: `2026-09-26`
External inspiration: Hermes Bot Mode.

### Problem / motivation

Different models and agents are strong at different tasks, but a single omnipotent agent profile creates excessive permissions, context pollution and unclear responsibility.

### Target concept

Support bounded bot/profile instances with separately declared:

- executor/model;
- capabilities;
- memory namespace;
- tools/MCP adapters;
- credentials;
- filesystem/network permissions;
- resource budget;
- allowed task types;
- validation gates.

Profiles should be capability-oriented rather than personality-oriented. Candidate examples include:

- research collector;
- coding executor;
- legal-authority analyst;
- reviewer/red-team agent;
- local utility agent;
- rendering/document agent.

### Acceptance criteria

- profile memory is isolated unless an explicit sharing contract exists;
- credentials are scoped per profile;
- cross-agent communication is typed/auditable;
- no profile can broaden its own permissions;
- profile identity and executor identity are captured in provenance;
- profile outputs remain untrusted until normal LUKART validation accepts them.

## IDEA-025 — Provider-Neutral Local Model Serving Layer

Status: `DEFERRED / HIGH-VALUE RESEARCH CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Directly coupling Product code to one local runtime such as Ollama would create avoidable lock-in. LUKART should consume local inference through a replaceable provider contract.

### Target concept

Introduce a local-model adapter boundary compatible with OpenAI-style APIs where practical.

Candidate runtime progression:

1. Ollama / llama.cpp for simple workstation deployment;
2. vLLM for higher-throughput or multi-user/model-server scenarios;
3. future runtimes behind the same provider contract.

The provider contract should capture:

- runtime/provider identity;
- model identity;
- quantization;
- context size;
- hardware requirements;
- latency/throughput;
- deterministic parameters where available;
- health status;
- privacy boundary;
- capability certification.

### Acceptance criteria

- Product logic does not depend on Ollama/vLLM-specific semantics outside adapters;
- model/runtime changes are explicit and measurable;
- unsupported context/capability fails closed;
- local endpoints are not assumed secure merely because they run locally;
- benchmark evidence is required before assigning production capabilities.

## IDEA-026 — Trading/Autonomous Bot Patterns as Architecture-Only Research

Status: `DEFERRED / INSPIRATION-ONLY`
Recorded: `2026-09-26`

### Problem / motivation

Several reviewed videos demonstrate autonomous trading agents, TradingView/webhook execution and 24x7 loops. These materials are useful as architecture patterns, but their profitability claims are not evidence suitable for LUKART adoption.

### Reusable patterns

- event/webhook-driven execution;
- scheduler-based routines;
- read-only/shadow first cycle;
- explicit ledger;
- monitoring and alerts;
- risk/budget limits;
- kill switch;
- staged promotion from observation to active execution.

### Boundary

LUKART may reuse these operational patterns for agent automation, but should not treat trading-video outcomes as validation of financial performance or self-improving autonomy.

## IDEA-027 — Sovereign Execution Fabric (15+ Year Agent Control Plane)

Status: `DEFERRED / STRATEGIC CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

The long-term risk is not lack of another agent framework. It is coupling LUKART to transient model/provider/runtime semantics. Over a 15+ year horizon, model vendors, APIs, agent frameworks, pricing, limits and protocols will change repeatedly.

### Target concept

Define a LUKART-owned Sovereign Execution Fabric (SEF) with three strictly separated planes:

1. **Authority Plane** — CCL, verified evidence, Legal Authority Fabric, jurisdiction/rule identities, release/trust policy.
2. **Control Plane** — capability routing, budgets, authorization, task ledger, certification, scheduling, memory policy, protocol adapters.
3. **Execution Plane** — replaceable local/remote models and agents such as Hermes, Codex, Work, Sol/Astra, local inference servers and future providers.

Execution Plane components are never authorities.

### Design rule

LUKART internal contracts remain stable and versioned. External ecosystems are connected by adapters. Provider-specific concepts may not leak into Authority Plane schemas.

### Acceptance criteria

- any executor can be removed without rewriting Product truth semantics;
- every execution route is policy-bound, versioned and replayable;
- no provider outage or product retirement destroys task/evidence continuity;
- migrations between runtime generations are covered by deterministic compatibility tests;
- the architecture supports local-only degraded operation for bounded capabilities.

## IDEA-028 — Proof-Carrying Agent Execution Receipt

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

A model output alone is insufficient evidence of how a result was produced. Future reproducibility requires more than model name plus prompt text.

### Target concept

Every material agent execution should emit a content-addressed receipt binding, where applicable:

- task/capability identity;
- input/evidence digests;
- code/config/schema/policy digests;
- executor/provider/model/version/quantization identity;
- tool/MCP/A2A adapter identities;
- memory/context snapshot digest or explicit no-memory state;
- budget reservation and measured consumption;
- start/end time and runtime class;
- output digest;
- validation findings;
- fallback/escalation path;
- human/independent approval references where genuinely present.

The receipt proves execution identity/provenance, not factual or legal truth.

### Acceptance criteria

- materially different execution conditions produce a different receipt identity;
- incomplete identity cannot claim identical replay;
- receipt verification works offline for stored artifacts where feasible;
- no executor can self-declare trusted validation evidence;
- receipts can survive provider replacement through stable LUKART schemas.

## IDEA-029 — Capability Certification Matrix and Executor Escrow Corpus

Status: `DEFERRED / STRATEGIC CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Routing by model brand or generic benchmark is unsafe. A model may be excellent at coding but poor at legal citation verification, or strong at English while weak in Polish procedural terminology.

### Target concept

Maintain a versioned capability certification matrix keyed by:

`capability × jurisdiction/language × executor/model/version × toolset × context class`.

Before an executor is eligible for a production capability, run it against a fixed/versioned escrow evaluation corpus containing focused, adversarial, regression and abstention cases.

Candidate outcomes:

- `CERTIFIED`;
- `SHADOW_ONLY`;
- `RESEARCH_ONLY`;
- `REJECTED`;
- `EXPIRED_REVALIDATION_REQUIRED`.

### Acceptance criteria

- provider/model upgrades do not inherit prior certification automatically;
- certification is evidence-bound and time/version limited where appropriate;
- route selection uses capability certification, not marketing/model rankings;
- difficult legal capabilities require independently reviewed evaluation material where necessary;
- local/cheap models may be certified for narrow tasks without being trusted globally.

## IDEA-030 — Protocol Neutrality Bridge: Internal Contract + MCP/A2A Adapters

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Open protocols improve interoperability, but directly making Product logic depend on MCP or A2A would replace vendor lock-in with protocol-version lock-in.

### Target concept

Use a stable LUKART internal capability/task envelope and implement protocol adapters around it:

- MCP adapter for tools/resources where appropriate;
- A2A adapter for interoperable agent-to-agent task exchange;
- native/local adapters for deterministic tools and local runtimes;
- future protocol adapters without changing Product authority contracts.

### Acceptance criteria

- protocol version changes are isolated to adapters/migrations;
- unknown capabilities/schema/extensions fail closed;
- remote agent discovery never implies authorization;
- A2A/MCP messages are untrusted boundary inputs until validated;
- protocol conformance tests are separate from LUKART semantic/capability certification.

## IDEA-031 — Epistemic Memory Firewall

Status: `DEFERRED / STRATEGIC SAFETY CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Persistent memory systems such as Honcho-style context stores can improve continuity while also amplifying stale, incorrect or cross-context statements over months or years.

### Target concept

Place an epistemic firewall between memory retrieval and trusted reasoning.

Memory entries are classified into at least:

- preference/workflow context;
- historical task context;
- unverified factual recollection;
- pointer to authoritative evidence;
- expired/stale candidate;
- prohibited/sensitive class.

A memory may influence convenience/routing, but a trust-sensitive factual/legal conclusion must resolve back to authoritative evidence/source identities.

### Acceptance criteria

- remembered legal/factual statements cannot become FACT merely through repetition;
- memory retrieval records source/provider and age;
- stale/conflicting memory is surfaced, not silently merged;
- case boundaries and tenant boundaries remain enforced;
- memory provider loss does not destroy Authority Plane data.

## IDEA-032 — Risk-Tiered Heterogeneous Quorum and Shadow Replay

Status: `DEFERRED / RESEARCH CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Using multiple agents for every task is wasteful, while trusting one executor for high-impact ambiguous decisions can create correlated failure.

### Target concept

Introduce risk-tiered execution:

- low risk: one certified cheapest/local executor;
- medium risk: primary executor + deterministic verifier;
- high risk: heterogeneous independent executors or generator/reviewer split + deterministic/legal validation;
- critical/novel: shadow replay on alternate executor before promotion, plus human/independent review where required.

Quorum disagreement is an explicit signal, not a majority-vote truth mechanism.

### Acceptance criteria

- quorum use is policy/risk triggered, not default;
- independent paths do not share hidden mutable memory where independence matters;
- disagreement yields `UNRESOLVED/REVIEW_REQUIRED` rather than forced consensus;
- cost/latency impact is measured;
- correlated provider/model-family failures are considered.

## IDEA-033 — Long-Horizon Compatibility and Provider Exit Harness

Status: `DEFERRED / STRATEGIC CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

A 15+ year system must assume provider retirement, API deprecation, model disappearance, incompatible schemas and loss of hosted features.

### Target concept

Maintain recurring exit drills and compatibility fixtures proving that critical bounded workflows can migrate between:

- remote provider A → remote provider B;
- remote → local model;
- one memory provider → another/no memory;
- one tool protocol/version → another adapter version;
- current runtime → archived replay mode.

Store stable synthetic fixtures and expected semantic outcomes for these drills.

### Acceptance criteria

- at least one bounded critical workflow remains executable without any single named AI vendor;
- provider retirement has a documented migration path;
- archived receipts/artifacts remain verifiable after executor disappearance;
- migration changes do not silently alter legal/epistemic meaning;
- exit drills are measured periodically rather than assumed.

## IDEA-034 — Legal-Domain Maturity Gate Before Further Agent Complexity

Status: `DEFERRED / STRATEGIC PRIORITY CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Current strategic asymmetry remains:

`Assurance / infrastructure maturity > verified legal-domain maturity`.

Adding increasingly sophisticated agents, memory and orchestration can amplify throughput without improving legal correctness.

### Target concept

Before activating major new autonomous/multi-agent capabilities, require measurable progress in the legal-domain maturity program, especially:

- authoritative source coverage/freshness;
- proposition-to-authority verification;
- procedural rule correctness;
- deadline/filing-route correctness;
- jurisdiction/version binding;
- legal Gold/adversarial corpus;
- abstention quality.

### Acceptance criteria

- agent throughput is not used as a proxy for legal quality;
- legal correctness metrics are tracked independently from CI/engineering PASS;
- new autonomy that increases blast radius requires corresponding domain-validation maturity;
- architecture work may proceed in research/shadow mode while legal maturity gates production activation.

## IDEA-035 — Polish Statutory Retrieval Benchmark Lab

Status: `DEFERRED / STRATEGIC HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
Primary target: LUKART ROS
Research inspiration: fresh 2026 Polish statutory-retrieval work comparing lexical, dense, hybrid, surrogate and reranking strategies.

### Problem / motivation

For legal reasoning, retrieval quality can dominate final answer quality. A stronger generator cannot reliably repair the wrong statute, wrong provision or missing controlling authority returned upstream.

### Target concept

Create a reproducible Polish legal retrieval benchmark over versioned statutory snapshots and controlled questions.

Benchmark candidate strategies:

- BM25 / lexical retrieval;
- dense retrieval;
- hybrid lexical+dense;
- reranking;
- surrogate/annotation-assisted retrieval;
- DTF-like low-cost retrieval pipelines;
- later graph/multi-hop retrieval only if the benchmark demonstrates a material gap.

### Required measurements

- Hit@1 / Hit@k;
- MRR / nDCG where appropriate;
- controlling-provision recall;
- latency;
- cost;
- index size;
- freshness/update cost;
- robustness to paraphrase, noisy facts and outdated-law traps.

### Acceptance criteria

- no retrieval strategy becomes canonical without measured evidence;
- benchmark corpus/source identities are versioned and content-addressed;
- temporal version of each legal source is explicit;
- benchmark distinguishes retrieval failure from reasoning failure;
- local/cheap retrievers may win production routing when quality is sufficient.

## IDEA-036 — Legal Temporal Applicability Engine

Status: `DEFERRED / P0 LEGAL-DOMAIN CANDIDATE`
Recorded: `2026-09-26`
Primary target: LUKART ROS

### Problem / motivation

A legally correct citation can still be wrong for the case if the cited provision was not in force on the relevant date, transitional rules apply, or the procedural event is tied to a different legal version.

### Target concept

Introduce an explicit temporal applicability layer binding:

- legal source identity;
- version identity;
- publication date;
- effective-from;
- effective-until;
- repeal/supersession relation;
- event/fact date;
- procedural trigger date;
- transitional/intertemporal rule identity;
- evaluation time.

The engine should answer not only `which rule?` but `which version of which rule applies to which event and why?`.

### Acceptance criteria

- current-law text cannot silently substitute for historically applicable law;
- unknown/ambiguous temporal applicability returns explicit non-PASS;
- every material legal conclusion binds the evaluated legal-version identity;
- temporal changes invalidate dependent reasoning/replay evidence;
- adversarial corpus includes repealed, amended and transitional-rule cases.

## IDEA-037 — Grounding, Citation and Abstention Composite Gate

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
Primary target: LUKART ROS

### Problem / motivation

Citation correctness, proposition support and justified abstention are related but distinct. A real citation may not support the claimed proposition; a grounded answer may still be incomplete; an unsupported answer should abstain rather than fabricate.

### Target concept

Create a composite validation pipeline:

```text
candidate legal output
→ source identity verification
→ quotation/section verification
→ proposition-to-source support
→ temporal applicability
→ grounding sufficiency
→ contradiction/open-question check
→ abstention decision
```

Possible result states include:
`VERIFIED`, `PARTIALLY_GROUNDED`, `MISMATCH`, `STALE`, `INSUFFICIENT_EVIDENCE`, `UNVERIFIABLE`, `ABSTAIN_REQUIRED`.

### Acceptance criteria

- generator and validator roles are separated where material;
- model memory is never accepted as legal-source evidence;
- unsupported confidence cannot pass;
- abstention quality is measured as a first-class metric;
- composite PASS binds exact source and validator identities.

## IDEA-038 — Legal Scenario Factory with Deterministic Gold Solver

Status: `DEFERRED / STRATEGIC HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
Primary targets: LUKART ROS + Synthetic Test Data Factory
Research inspiration: dynamic legal-task generation with deterministic/symbolic gold.

### Problem / motivation

Static hand-authored legal Gold sets are expensive, small and prone to memorization. They also under-cover combinatorial fact patterns and procedural edge cases.

### Target concept

Build a rule-driven `Legal Scenario Factory`:

```text
versioned fact generator
+ versioned procedural/legal rule pack
+ deterministic/symbolic solver
→ expected legal/procedural state
→ generated adversarial scenario
```

Initial candidate families:

- ZUS appeals;
- contribution decisions/remission/installments;
- WSA/NSA procedural routing;
- deadlines;
- service/delivery events;
- enforcement;
- KRS/registry matters;
- jurisdiction and standing traps.

### Acceptance criteria

- generated facts remain schema-valid and legally coherent;
- deterministic expected state is traceable to rule/source identities;
- generator diversity is measured;
- train/evaluation separation prevents benchmark contamination;
- synthetic difficulty and error distribution are compared with reviewed real/anonymized cases where legally permissible.

## IDEA-039 — Retrieval Strategy Registry and Evidence-Based Selection

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
Primary targets: LUKART ROS + LUKART WORK

### Problem / motivation

There is no universal best retrieval stack. Hybrid search, reranking, graph retrieval or semantic chunking can improve one corpus and harm another.

### Target concept

Treat retrieval as a replaceable, benchmarked capability rather than a fixed architecture decision.

Registry metadata should include:

- strategy identity/version;
- corpus/domain class;
- chunking/structure policy;
- embedding/reranker identity;
- thresholds;
- measured quality;
- measured latency/cost;
- known failure modes.

### Acceptance criteria

- no GraphRAG/hybrid/reranker component is promoted by convention alone;
- corpus-specific winner is selected by measured downstream quality;
- threshold changes are versioned;
- retrieval strategy changes trigger regression evaluation;
- historical results remain reproducible from registry identity.

## IDEA-040 — Parser Shadow Benchmark and Outcome-Based Document Ingestion

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
Primary target: LUKART WORK

### Problem / motivation

A parser can produce visually clean Markdown while silently damaging tables, headings, coordinates or downstream retrieval. Parser quality should therefore be judged by downstream utility, not aesthetics alone.

### Target concept

Run multiple parsers/paths in shadow benchmark mode against representative document classes:

- native-text extraction;
- Docling-like structured parsing;
- Marker/MinerU-class alternatives;
- OCR/VLM fallback;
- table/layout-specialized paths.

Measure:

- field accuracy;
- section/hierarchy preservation;
- table fidelity;
- source-coordinate fidelity;
- downstream retrieval/QA accuracy;
- latency/cost;
- failure/abstention behavior.

### Acceptance criteria

- parser selection is document-class aware;
- no parser becomes global default without evidence;
- final ingestion preserves provenance coordinates;
- low-confidence extraction fails closed or escalates;
- parser changes run downstream regression, not only parser-unit tests.

## IDEA-041 — Synthetic Data Quality Contract v2

Status: `DEFERRED / STRATEGIC HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`
Primary target: Synthetic Test Data Factory

### Problem / motivation

Schema-valid synthetic data can still be unrealistic, low-diversity, privacy-leaking or too easy/hard compared with the real task.

### Target concept

Extend synthetic quality evaluation across:

- validity;
- fidelity;
- diversity;
- privacy leakage risk;
- downstream difficulty;
- agent/model ranking stability;
- outcome/state verification;
- rare/edge-case coverage.

Where agent tasks are generated, success should be checked against actual sandbox/database/API end state rather than only LLM-as-a-judge prose scoring.

### Acceptance criteria

- privacy-risk tests include membership/identity-style attacks where applicable;
- synthetic benchmark preserves relative task difficulty within defined tolerance;
- generated tasks have deterministic or externally verifiable terminal conditions when feasible;
- quality metrics are versioned and thresholded;
- generation method changes require fresh validation.

## IDEA-042 — Final-Artifact ATS Re-Parse Gate

Status: `DEFERRED / CROSS-PROJECT CANDIDATE`
Recorded: `2026-09-26`
Primary target: LATAM Career OS

### Problem / motivation

A CV may look excellent to a human while the final PDF is parsed poorly by an ATS. Validation must test the rendered artifact, not only source text.

### Target concept

Add a final-artifact pipeline:

```text
CV source
→ structural/ATS checks
→ JD matching
→ rendering
→ final PDF
→ local ATS re-parse
→ field/section comparison
→ PASS / repair
```

Candidate evaluation dimensions:

- name/contact extraction;
- section recognition;
- chronology;
- employer/role parsing;
- skills extraction;
- multi-column/sidebar robustness;
- language handling;
- final rendered-text fidelity.

### Acceptance criteria

- ATS validation runs on the exact delivered PDF;
- extraction mismatches feed a repair loop;
- scoring logic is transparent and versioned;
- no proprietary ATS score is treated as ground truth without evidence;
- Colombia/Spanish-specific corpus is added before production claims.

## IDEA-043 — CO Source & Authority Matrix v1

Status: `DEFERRED / RESEARCH BASELINE CREATED`
Recorded: `2026-09-26`
Research artifact: `docs/research/CO_SOURCE_AUTHORITY_MATRIX_V1.md`

### Problem / motivation

Colombia has multiple legal, judicial, pension, contribution, social-protection and health sources. Without a source/authority map, implementation risks ad-hoc scraping, duplicated adapters and incorrect authority assumptions.

### Target concept

Maintain a Colombia source matrix covering:

- institution/source;
- access/API/web mode;
- authority class;
- temporal capability;
- privacy class;
- adapter candidate;
- fallback/corroboration;
- fail-closed semantics.

SUIN-Juriscol is explicitly retained as a high-value official consolidated legal/temporal source. Its role is complementary to primary publication evidence such as Diario Oficial.

### Acceptance criteria

- every Colombia integration maps to a declared source class and trust boundary;
- no source is silently treated as universally authoritative for all propositions;
- privacy-sensitive portals require case-scoped authorization;
- transport/API instability is separated from legal authority semantics;
- matrix is revalidated before Colombia implementation begins.

## IDEA-044 — Jurisdiction Adapter SDK / ExternalSourceAdapterV1

Status: `DEFERRED / STRATEGIC ACCELERATION CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Building a custom agent/integration for every institution creates repeated work and long-term maintenance risk.

### Target concept

Create one reusable SDK/contract for external legal/administrative sources. Each country/provider becomes a thin adapter over the same envelope.

Common capabilities should include:

- source/institution identity;
- jurisdiction;
- source class;
- exact locator/document identity;
- content/source digest;
- adapter/parser/schema identity;
- temporal metadata;
- privacy classification;
- authorization evidence;
- coverage/completeness declaration;
- explicit failure state;
- fallback/corroboration pointers.

Transport implementations may be REST, Socrata, HTML, MCP, browser automation or authenticated portal access without changing the Product authority model.

### Acceleration objective

After the SDK and conformance suite exist, new integrations should primarily require:

`adapter + fixtures + source-specific tests + authority policy`

instead of a new bespoke subsystem.

## IDEA-045 — Portfolio Execution Accelerator with WIP Limits

Status: `DEFERRED / OPERATING-MODEL CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

The project now has more valuable ideas than can be implemented safely in parallel. Excessive simultaneous work would increase context switching, incomplete stages, duplicated infrastructure and governance drift.

### Target concept

Use a portfolio funnel:

```text
IDEA
→ RESEARCHED
→ MEASURED
→ READY
→ ACTIVE
→ VALIDATED
→ CLOSED
```

with explicit WIP limits.

Recommended delivery lanes:

1. `LEGAL-CORRECTNESS` — authority, retrieval, citations, temporal law, procedural rules;
2. `EXECUTION-FABRIC` — routing, local/remote models, memory, execution receipts;
3. `DOCUMENT/WORK` — parsing, provenance, rendering, filing workflow;
4. `EVALUATION/DATA` — Gold, scenario factory, synthetic test data;
5. `JURISDICTION-PACKS` — PL/EU first, CO research/shadow until activation.

At any time, only a small bounded number of implementation stages are ACTIVE. Research can continue in parallel but cannot silently expand implementation scope.

### Acceptance criteria

- every active stage has a measurable decision need and dependency map;
- no new implementation begins merely because an idea is attractive;
- shared primitives are implemented before duplicated jurisdiction-specific equivalents;
- WIP/blocked state is visible;
- closure precedes activation of the next dependent stage.

## IDEA-046 — Vertical Slice Accelerator

Status: `DEFERRED / HIGH-VALUE CANDIDATE`
Recorded: `2026-09-26`

### Problem / motivation

Broad platform integrations delay evidence. A thin end-to-end slice can validate shared architecture faster than integrating every source first.

### Target concept

For each major capability/jurisdiction, implement one narrow representative path through all required layers.

Example Colombia public-law slice:

```text
legal question
→ SUIN/Función Pública discovery
→ exact norm identity
→ temporal/vigencia metadata
→ Diario Oficial corroboration when material
→ related court source
→ citation/grounding verification
→ execution receipt
→ final answer
```

Only after this slice passes should additional Colombian courts or private social-security connectors be added.

### Acceptance criteria

- slice crosses real authority, temporal, retrieval, validation and provenance boundaries;
- synthetic fixtures precede private-data integrations;
- architecture gaps found by the slice are fixed in shared core before broad expansion;
- the slice is benchmarked for quality, latency and resource cost.

## IDEA-047 — Post-Current-Projects Reprioritization Gate

Status: `DEFERRED / OWNER STRATEGY`
Recorded: `2026-09-26`

### Owner decision

Current projects should be completed before launching the accumulated strategic backlog as new implementation programs.

After current project completion, perform a fresh portfolio review against live repository state and current external technology/source landscape.

### Reprioritization inputs

- current legal-domain maturity;
- current blockers and technical debt;
- reusable primitives already implemented;
- newest legal-AI/retrieval research;
- source/API changes in Poland/EU/Colombia;
- cost/resource limits;
- business value and user demand;
- dependency graph;
- risk reduction per unit of implementation effort.

### Decision rule

Do not preserve today's implementation ordering as immutable. Preserve the ideas and evidence, then re-rank them with fresh measurements when execution capacity becomes available.

## Backlog capture policy — owner decision

Recorded: `2026-09-26`

Owner instruction: material new ideas arising during LUKART ROS research, architecture, implementation review, external-source analysis or cross-project learning should be captured automatically in this backlog without requiring a separate confirmation each time.

Capture rules:

- add only ideas with concrete architectural, legal-domain, operational, evaluation, interoperability, reliability or implementation value;
- avoid duplicates; extend an existing idea when the new insight is materially the same concept;
- keep speculative/low-signal observations out of the backlog until they cross a meaningful evidence threshold;
- mark every captured item as non-authoritative until separately researched/measured/implemented/validated;
- preserve live GitHub/main and `docs/WORKING_PRINCIPLES.md` as authoritative implementation/governance state;
- major ideas may also receive a dedicated research/ADR artifact when depth, trade-offs or evidence justify it;
- automatic capture never authorizes implementation, merge, production activation or policy weakening.

## External repository disposition from 2026-09-26 review

- `planning-with-files`: `ADOPT CONCEPT / DEEP REVIEW CANDIDATE`;
- OmniRouter: `RESEARCH-ONLY` — do not replace LUKART `CapabilityRouter`;
- Agent Reach: `RESEARCH-ONLY / ADAPTER PATTERN`;
- Orka/multi-agent workbench: `CONCEPT-ONLY` — avoid a second orchestration authority without a measured gap;
- OpenMontage: `REJECT FOR CORE / POSSIBLE FUTURE MARKETING TOOL`;
- OpenSEO: `REJECT FOR CORE / POSSIBLE FUTURE PRODUCT-MARKETING TOOL`;
- No-AI-Slop-style checking: `OPTIONAL RENDERING/QUALITY RESEARCH`;
- God's Eye-style visualization: `REJECT FOR CORE / INSPIRATION-ONLY`.

## Review boundary — rendered-document labels

Owner decision recorded `2026-09-19`: the proposal to add visible labels such as `REVIEW_REQUIRED`, `REVIEWED`, `AI-generated`, `Wygenerowano przez LukArt RoS`, or visible provenance statements to final legal/client documents is rejected.

This backlog does not authorize such labels. Internal provenance, identity and audit evidence may exist within LUKART system metadata/evidence boundaries, but must not be rendered into final documents merely because an artifact was produced with LUKART assistance.
