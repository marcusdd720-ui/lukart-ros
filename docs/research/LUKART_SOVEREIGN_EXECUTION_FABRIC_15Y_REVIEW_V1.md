# LUKART ROS — Sovereign Execution Fabric 15+ Year Architecture Review v1

Status: RESEARCH / ARCHITECTURE PROPOSAL
Recorded: 2026-09-26
Authority: non-authoritative research artifact. Canonical engineering authority remains `docs/WORKING_PRINCIPLES.md`; live repository state remains GitHub.

## 1. Decision need

Determine whether recent agent/runtime patterns (JARVIS-style assistants, Jev/System-One routing, Hermes/OpenClaw memory and bot modes, local models, Ollama/vLLM, Antigravity, MCP/A2A and 24x7 autonomous-agent patterns) justify a material change to LUKART ROS architecture for a 15+ year horizon.

## 2. Conclusion

The correct long-horizon target is **not** a clone of Hermes/JARVIS/OpenClaw and not a single-model agent OS.

The best-justified direction is a **Sovereign Execution Fabric (SEF)** owned by LUKART:

```text
AUTHORITY PLANE
CCL / Evidence / Legal Authority / Jurisdiction Rules / Trust Policy
                        │
                        ▼
CONTROL PLANE
Capability Router / Certification / Budgets / Task Ledger / Memory Policy
Protocol Adapters / Scheduling / Authorization / Execution Receipts
                        │
                        ▼
EXECUTION PLANE
Local deterministic tools / local models / Hermes / Codex / Work
Sol-Astra-class models / future providers / remote A2A agents
```

Execution components remain replaceable workers, never Product authorities.

## 3. Highest-priority weakness

The largest overall project weakness is **not lack of agent sophistication**.

The strategic asymmetry is:

`assurance/governance maturity > verified legal-domain maturity`.

LUKART has strong controls for exact-SHA, provenance, replay, trust boundaries, recovery and fail-closed engineering. The remaining product risk is that sophisticated infrastructure can preserve and reproduce a legally incorrect or stale conclusion if legal-source coverage, proposition-to-authority verification, procedural rules, deadlines, filing routes and legal Gold validation lag behind.

Therefore agent/runtime expansion should proceed in research/shadow mode while legal-domain maturity is raised in parallel.

## 4. What recent technologies actually contribute

### Jev / System-One decision models

Useful for bounded typed decisions: routing, classification, scoring, retry/escalation and resource selection. They should not replace deterministic policy where deterministic rules are sufficient.

Adopt pattern: **fast classifier before expensive executor**.
Do not adopt: brand-specific routing authority.

### Laya and future local decision models

Useful as a provider-neutral/local candidate for narrow routing tasks. Must be independently benchmarked on LUKART workloads; third-party or author benchmarks are insufficient for certification.

### Hermes / Bot Mode

Useful patterns: isolated profiles, per-bot memory/toolsets/credentials, recurring routines and multi-model execution.

Adopt pattern: bounded profile/runtime isolation.
Do not adopt: Hermes as LUKART authority/control plane.

### Honcho / persistent memory

Useful for continuity, user/project preferences and historical task retrieval.

Adopt only behind an **Epistemic Memory Firewall**. Memory remains contextual/untrusted and cannot establish legal/case truth.

### Antigravity / local agents

Confirms that local agent execution is becoming a first-class industry direction. LUKART should support local execution but own its provider contract.

### Ollama / llama.cpp / vLLM

Useful execution runtimes, not architecture authorities.

Recommended progression:
1. workstation/simple local serving: Ollama/llama.cpp;
2. higher-throughput service: vLLM or future compatible runtime;
3. always behind a LUKART provider adapter.

### MCP

Use as an interoperability protocol for tools/resources where useful.
Never let MCP server discovery imply trust/authorization.

### A2A

Use as an adapter for external/remote agent collaboration.
Never let A2A discovery imply capability certification or authority.

### JARVIS-style assistants

Voice, PC control, wake words, screen vision and UX are feasible, but they are presentation/operator surfaces. They should not be the core architecture.

### 24x7 autonomous bots

Reusable patterns: scheduler, event/webhook ingestion, shadow mode, ledger, budgets, alerts, kill switch and staged promotion.

Reject the idea that continuous autonomous operation itself proves correctness or profitability.

## 5. Hardcore enterprise architecture

### 5.1 Stable internal contract

All executors consume/produce a LUKART-owned versioned task envelope. External provider schemas are translated at adapters.

Minimum identity should include:
- capability;
- input schema;
- output schema;
- input/evidence digests;
- policy/config/schema identities;
- executor/provider/model/version;
- tool/protocol adapter identities;
- resource budget;
- memory/context identity;
- authorization evidence.

### 5.2 Proof-Carrying Agent Execution

Every material run emits an immutable/content-addressed execution receipt.

A receipt proves **how** a result was produced; it does not prove that the result is factually or legally correct.

### 5.3 Capability certification, not model ranking

Routing must be based on a capability certification matrix rather than generic "best model" rankings.

Certification key:

`capability × jurisdiction/language × executor/version × toolset × context class`.

Model/provider upgrades require revalidation.

### 5.4 Risk-tiered routing

Low risk:
- deterministic/local cheapest certified executor.

Medium:
- primary executor + deterministic verification.

High:
- heterogeneous generator/reviewer paths and legal validation.

Critical/novel:
- shadow replay + explicit human/independent evidence where required.

Disagreement remains an explicit unresolved state.

### 5.5 Memory quarantine

Memory may accelerate context retrieval but cannot bypass authoritative sources.

Trust-sensitive recalled facts must resolve to authoritative evidence/source identities.

### 5.6 Protocol neutrality

MCP/A2A are adapters, not internal truth models. Their version changes must not force migrations of CCL/legal authority semantics.

### 5.7 Provider exit

The system must regularly prove a bounded critical workflow can survive:
- provider retirement;
- remote-to-local migration;
- memory-provider removal;
- protocol upgrade;
- model-version replacement.

## 6. What should NOT be built

Do not build:
- one giant omnipotent agent;
- a second truth store in memory;
- provider-specific Product schemas;
- majority-vote truth from agents;
- automatic self-improvement with self-approval;
- direct autonomous writes to trusted legal/epistemic state;
- an always-on agent with unrestricted credentials/filesystem/network;
- a system whose operation requires one named AI vendor.

## 7. Proposed innovation frontier

The most promising differentiated LUKART direction is the combination of:

1. **Sovereign Execution Fabric** — vendor-neutral control plane.
2. **Proof-Carrying Agent Execution** — cryptographically/content-addressed execution identity.
3. **Capability Escrow Certification** — production eligibility proven on fixed LUKART corpora.
4. **Epistemic Memory Firewall** — persistent memory without memory-as-truth.
5. **Counterfactual Provider Replay** — continuously test whether a workflow remains semantically stable after model/provider substitution.
6. **Risk-Tiered Heterogeneous Quorum** — redundancy only when consequence/risk justifies it.
7. **Provider Exit Drills** — treat vendor independence as a tested operational capability rather than an architectural claim.

The combination, rather than any individual technology, is the potential pioneer-level differentiator.

## 8. Recommended order

### Priority A — legal-domain correctness
- Verified Legal Authority Fabric;
- Citation Verification Gate;
- procedural rule packs;
- deadline/filing-route correctness;
- legal Gold/adversarial corpus;
- legal-domain metrics.

### Priority B — execution sovereignty
- stable executor/provider contracts;
- execution receipt;
- capability certification matrix;
- budget-aware routing;
- local execution tier.

### Priority C — interoperability
- MCP tool adapter;
- A2A external-agent adapter;
- provider exit/migration harness.

### Priority D — advanced autonomy
- memory provider fabric + epistemic firewall;
- multi-agent worktree orchestration;
- controlled self-improvement;
- 24x7 routines;
- operator dashboard/voice/JARVIS-style UX.

## 9. Validation before implementation

Before promoting SEF into an implementation stage, require a Research Charter with measurable hypotheses.

Minimum experiments:
1. task-routing baseline vs classifier-assisted routing;
2. Work/API consumption reduction;
3. local-model capability benchmark;
4. executor swap semantic stability;
5. memory contamination/adversarial retrieval tests;
6. A2A/MCP untrusted-input tests;
7. provider-loss/exit drill;
8. legal-domain quality does not regress with cheaper/local routing.

## 10. Decision

**ADOPT ARCHITECTURAL DIRECTION, NOT IMPLEMENTATION YET.**

The architecture has logical value and addresses a real long-horizon gap, but implementation should be gated by measurement and by progress on legal-domain maturity. The correct next implementation is not "install Hermes/Jev/Laya"; it is to define and validate the smallest LUKART-native execution contract and capability-certification experiment that proves the SEF hypothesis.
