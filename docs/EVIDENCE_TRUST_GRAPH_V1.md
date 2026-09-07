# PHX-04 — Evidence Trust Graph v1

Status: Active engineering contract
Authority: deterministic read-only projection
Input authority: Canonical Case Ledger + Epistemic Projection v2

## Decision

Evidence Trust Graph is a content-addressed projection, not a database and not a writable
source of truth. Canonical Case Ledger remains the only authoritative writable history.
The graph may be discarded and rebuilt from exact CCL history, the exact Epistemic v2
projection and a versioned TrustPolicy.

`core/p3/semantic_graph.py` remains the semantic dependency/change-propagation component
for PHX-06. It is intentionally not repurposed as the Evidence Trust Graph because the
two graphs have different semantics and failure modes. No graph database or generic
event-sourcing framework is introduced.

## Identity

The graph identity binds:

- exact `CaseId`;
- exact CCL ledger head;
- exact Epistemic Projection v2 identity;
- exact TrustPolicy identity;
- canonically ordered nodes and edges.

Nodes are typed as EVENT, ASSERTION or DECISION and retain their exact content-addressed
source identity. A ledger-head or policy change therefore creates a different graph
identity.

## Edges

Derived edges are deterministic consequences of canonical epistemic history:

- SUPPORTS — an exact prior evidence event supports an assertion or transition decision;
- TRANSITIONS — an exact decision changes one assertion state;
- RECORDED_BY — assertion/decision identity is bound to its canonical recording event.

Sensitive trust relations are never inferred. They exist only after an explicit
`trust.relation.declared.v1` CCL event with a content-addressed relation declaration:

- CONTRADICTS;
- AUTHORIZED_BY;
- ATTESTED_BY.

An attestation records origin/integrity evidence. It does not promote CLAIM/HYPOTHESIS to
FACT and does not override EpistemicPolicy. Authorization likewise does not imply truth.

## Fail-closed boundaries

The graph rejects:

- foreign-case event input;
- stale Epistemic projection / ledger-head mismatch;
- dangling or cross-case node references;
- malformed/tampered relation identity;
- unknown `trust.*` event types;
- edge types denied by policy;
- semantic duplicate explicit edges;
- self-loop relations;
- node or edge counts beyond explicit hard limits.

Limits fail explicitly with `TRUST_GRAPH_NODE_LIMIT_EXCEEDED` or
`TRUST_GRAPH_EDGE_LIMIT_EXCEEDED`; history is never silently truncated.

## No write authority

`knowledge/evidence_trust_graph.py` imports CCL contracts only. It has no
`CanonicalCaseLedger`, `append_event`, database, mutation or persistence API. Callers that
need to declare a contradiction/authorization/attestation relation must record it through
the normal authorized Canonical Ledger boundary first; the graph only observes it.

## Validation

Engineering closure requires deterministic identity tests, exact FACT support edges,
explicit-only contradiction tests, attestation/authorization non-promotion tests,
cross-case/dangling/tamper/unknown-event/duplicate negative tests, stale projection tests,
policy identity binding, hard budget tests, strict MyPy coverage, full regression,
exact-SHA CI, guarded merge and post-merge validation.
