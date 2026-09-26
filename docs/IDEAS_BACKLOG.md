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
