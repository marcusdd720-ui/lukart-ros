# LUKART ROS — Semantic Change Propagation v2

Status: PHX-06 engineering contract
Authority: deterministic planning/projection only
Writable case SSOT: Canonical Case Ledger (CCL)
Replay authority: exact Case Replay v2 manifest identity

## Problem

A semantic input change can invalidate multiple downstream projections and results. The
legacy P3 semantic graph provides deterministic dependency planning, but its public
contract uses arbitrary string identifiers and does not impose hard node/depth/work
budgets. For a long-lived trust core, unbounded propagation and mutable/logical identity
references are not sufficient.

## Decision

PHX-06 adds a versioned, typed and bounded propagation layer over the existing
`SemanticChangeGraph` invariants. The legacy graph remains backward compatible; v2 does
not create another graph database, persistence store or Product truth authority.

Each v2 dependency endpoint is an `ImmutableArtifactRef` containing:

- exact `case_id`;
- typed artifact kind: EVENT, REVISION, EVIDENCE, PROJECTION or RESULT;
- exact content-addressed identity.

Logical/mutable object identifiers are not accepted as v2 dependency authority. Every
edge is case-scoped; cross-case edges fail closed.

## Propagation policy

`SemanticPropagationPolicyV2` is content-addressed and defines three hard budgets:

- `max_nodes` — maximum distinct affected artifacts, including changed roots;
- `max_depth` — maximum dependency distance from a changed root;
- `max_work` — maximum reverse dependency-edge inspections.

Exceeding any budget raises an explicit `BLAST_RADIUS_EXCEEDED` failure with reason
`NODES`, `DEPTH` or `WORK`. Propagation never silently truncates an affected set.

The implementation checks the depth boundary before discarding deeper dependents and
checks node/work budgets before accepting work beyond the configured limit. Therefore a
partial result cannot be mistaken for a complete revalidation plan.

## Plan identity

A `SemanticPropagationPlanV2` binds:

- exact case identity;
- exact changed and affected immutable references;
- optional deterministic materialized paths;
- exact graph identity;
- exact propagation-policy identity;
- exact Case Replay v2 manifest identity;
- observed work and depth counters;
- content-addressed plan identity.

The replay binding can be checked explicitly; a stale/wrong replay manifest fails closed.
Changing a dependency, policy, changed artifact, replay identity or traversal result
changes the plan identity.

## Recompute lineage

Recomputation never mutates a published result. `RecomputeLineageV2` creates a new derived
result identity from:

- propagation plan identity;
- replay manifest identity;
- previous result identity;
- recomputed content identity.

The content digest can remain identical when semantics are unchanged, while the derived
result identity remains lineage-bound to the recomputation event. This preserves the
important distinction between content identity and derived-result history.

## Trust boundaries

- CCL remains the only writable case-history SSOT.
- Semantic propagation has no CCL append API and no persistent truth store.
- Existing P3 graph cycle/self-reference invariants are reused rather than forked.
- v2 dependencies use exact content identities, not model/provider guesses.
- Cross-case propagation is denied until a separately versioned authorization contract
  explicitly permits it.
- Replay identity is explicit; stale replay evidence cannot silently validate a new plan.
- `BLAST_RADIUS_EXCEEDED` is a hard failure and never a partial PASS.
- Recomputed outputs receive lineage-bound identities; historical results stay immutable.

## Alternatives considered

1. **Modify legacy `SemanticChangeGraph.plan()` in place** — rejected because changing its
   identifier and budget semantics would create avoidable backward-compatibility risk.
2. **Additive typed v2 layer over existing graph invariants** — selected. It preserves the
   tested legacy contract while adding exact identities, case isolation and bounded
   traversal where required.
3. **Graph database/event platform** — rejected. Current measured failure mode is semantic
   trust and bounded traversal, not graph-storage scale. A new platform would add a second
   persistence concern without improving the Product truth model.

## Required validation

Closure requires focused, adversarial and full regression tests plus exact candidate SHA
CI, guarded exact-head merge and post-merge validation. Negative coverage must include:

- cross-case dependency;
- self-edge and cycle;
- unknown changed exact reference;
- node/depth/work budget overflow;
- deep graph bounded failure;
- wrong replay identity;
- tampered policy identity;
- immutable recompute lineage;
- absence of CCL write/persistence authority.

External independent certification is not implied by engineering PASS.
