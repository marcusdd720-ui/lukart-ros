# LUKART UNIVERSUM — Sovereign Agent Fabric (LSAF)
Date: 2026-10-05
Status: CANONICAL IDEA PACKAGE / NOT YET IMPLEMENTED

## Purpose
Create a provider-independent, model-independent, 15+ year architecture for LUKART ROS, LUKART WORK, UAOS and future products.

## Core principles
- Stable contracts > current providers.
- Provider != product.
- Model != architecture.
- Skills/capabilities must be portable.
- Evidence before status.
- Planned != Implemented != Validated != Certified.
- Fail closed.
- Exact-SHA provenance.
- Deterministic validation before trust.
- Human authority remains explicit at protected gates.

## Target architecture
Products -> Product Contracts -> Sovereign Control Plane -> Capability Plane / Evidence Plane / Memory Plane -> Execution Plane -> provider adapters.

### Execution adapters
- CodexAdapter
- HermesAdapter
- ClaudeAdapter
- GeminiAdapter
- LocalAgentAdapter
- FutureAgentAdapter

### Workspace adapters
- native git worktree
- Workmux
- container/sandbox
- future VM/runtime backend

## New concepts to implement
1. Execution Truth Contract.
2. Agent Skills compatibility layer.
3. Provider Abstraction Contract.
4. Evidence Ledger.
5. Layered Memory M0-M6.
6. Capability Genome.
7. Execution Quorum.
8. Provider Darwinism / measured provider competition.
9. Autonomous BUILD-vs-ADOPT scanner.
10. Model Intelligence registry.
11. Self-hosted project intake pipeline.
12. Long-duration soak evidence.
13. Independent liveness verification.
14. Trust score derived from evidence, never self-declared.
15. Anti-entropy reconciler.
16. Time-travel execution replay.
17. Trust decay / mandatory revalidation.
18. Blast-radius budgets.
19. Degradation ladder.
20. Periodic vendor-extinction drills.

## Layered memory
M0 Immutable Evidence
M1 Project State
M2 Decisions / ADR
M3 Operational Memory
M4 Semantic Knowledge
M5 User Context
M6 Ephemeral Agent Context

LLM memory is never the source of truth.

## Capability Genome
Each capability should carry:
- capability_id and semantic version
- input/output contract
- invariants
- implementation type
- provider independence flag
- compatible executors
- source/test/benchmark provenance
- reliability/determinism/regression metrics
- security permissions
- network/filesystem/secrets boundaries
- economics/cost class
- lifecycle and last_verified

## Execution Quorum
Critical outputs should be split into:
- builder/drafter
- independent verifier
- adversarial/red-team reviewer
- deterministic validator

A protected output reaches SEND_READY only when mandatory invariants pass and quorum requirements are satisfied.

## Provider Darwinism
Providers compete on measured quality, reliability, latency, tool-use, privacy and cost.
Paid fallback is BLOCKED unless explicitly authorized.
No product architecture may require one named model when a capability threshold can be specified instead.

## Long-term objective
LUKART must survive model, API, framework and vendor replacement without rewriting product logic.
