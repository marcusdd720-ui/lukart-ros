# Existing IDEAS_BACKLOG → LSAF Integration Map
Date: 2026-10-05
Status: PLANNING PROJECTION / NON-AUTHORITATIVE

## Authority rule

`docs/IDEAS_BACKLOG.md` remains the canonical parking lot for deferred ideas.
`docs/architecture/LSAF_IMPLEMENTATION_MANIFEST.yaml` is the current execution-planning projection for LSAF.
This map prevents duplicate ideas, lost history and competing sources of truth.

BACKLOG != IMPLEMENTATION.
A mapped idea is not promoted merely because it appears in the LSAF plan.

## Direct strategic mappings

| Existing idea | LSAF target |
|---|---|
| IDEA-011 Persistent Agent Work Ledger | task-state continuity / execution replay |
| IDEA-019 Multi-Agent Worktree Orchestrator | workspace isolation + orchestrator |
| IDEA-022 LUKART Agent Runtime as the Control Plane | LSAF Control Plane |
| IDEA-023 Local-First 24x7 Agent Execution Fabric | local/remote execution fabric |
| IDEA-027 Sovereign Execution Fabric | direct predecessor of LSAF |
| IDEA-028 Proof-Carrying Agent Execution Receipt | Evidence Ledger / execution receipt |
| IDEA-029 Capability Certification Matrix | Capability Genome + benchmark/certification |
| IDEA-030 Protocol Neutrality Bridge | MCP/A2A/provider-neutral adapters |
| IDEA-031 Epistemic Memory Firewall | layered memory M0-M6 + trust boundary |
| IDEA-032 Risk-Tiered Heterogeneous Quorum | Execution Quorum |
| IDEA-033 Long-Horizon Compatibility and Provider Exit Harness | vendor-extinction drills |
| IDEA-045 Portfolio Execution Accelerator with WIP Limits | portfolio prioritization / WIP policy |
| IDEA-046 Vertical Slice Accelerator | incremental integration strategy |
| IDEA-047 Post-Current-Projects Reprioritization Gate | current P0-before-LSAF ordering |
| IDEA-052 Ephemeral Capability Lease & Side-Effect Gateway | blast-radius budget / capability lease |
| IDEA-053 Hierarchical Cognitive Fabric | capability/risk-based routing |
| IDEA-054 Semantic Drift Firewall | semantic conformance / long-horizon compatibility |
| IDEA-074 LUKART WORK → LUKART ROS Modular-Monorepo Consolidation | product-adapter migration / ROS–WORK consolidation program |
| IDEA-076 LSAF Sovereign Trust Kernel | capability admission + execution truth convergence across Evidence Ledger, Capability Genome, Memory Firewall, Side-Effect Gateway and Anti-Entropy Reconciler |

## LSAF additions not intended to overwrite backlog concepts

The current LSAF plan adds or sharpens:

- Sovereign Trust Kernel convergence layer;
- Capability Passport with security/provenance/benchmark/expiry evidence;
- transactional attempt ledger + fencing-token leases;
- first-class UNCERTAIN side-effect state;
- Evidence-Carrying Memory and bitemporal legal knowledge;
- semantic documentation drift gate;
- Execution Truth Contract;
- Anti-Entropy Reconciler;
- Trust Decay;
- Degradation Ladder;
- Agent Skills compatibility;
- provider health/cost/latency telemetry;
- machine-readable implementation manifest;
- canonical Integration Intake Pipeline.

If one of these materially matches an existing backlog concept, extend the existing IDEA instead of creating a duplicate.

## Promotion policy

Before any mapped item moves from planning to implementation:
1. establish current decision need;
2. run BUILD-vs-ADOPT pre-audit where external technology is involved;
3. verify dependency ordering;
4. assign explicit owner/agent role;
5. create isolated branch/worktree;
6. define acceptance tests and evidence;
7. preserve exact-SHA review and promotion gates.

## Current priority boundary

Generator Pism > UAOS Execution Truth/soak > BUILD-vs-ADOPT > LSAF foundation.

The existence of this map does not authorize bypassing that order.
