# PRC-01 — Product Runtime Convergence v1

Status: `IMPLEMENTATION / VALIDATION PENDING`

## Problem

LUKART ROS already has a mature Post-Hardcore trust core: Canonical Case Ledger,
Epistemic Assertions/State v2, Evidence Trust Graph, Case Replay v2, bounded change
propagation, recovery, invariant verification and signed exchange. The older local
`CaseWorkspace` operator path also has FACT/LAW/DOSSIER/REVIEW and a cognitive release
boundary.

PRC-01 closes the architectural risk that these capabilities could remain parallel runtime
worlds. It defines one Product runtime proof over the canonical trust chain without
rewriting the existing components or creating another Product truth authority.

## Authority invariant

Canonical Case Ledger remains the sole authoritative writable SSOT for case history.
PRC-01 is derived and verification-only.

Canonical runtime chain:

`Evidence -> CCL -> Epistemic v2 -> Evidence Trust Graph -> Reasoning -> Result -> Replay -> ProductRuntimeProofV1`

`CaseWorkspace`, renderers, operator tools and future APIs are adapters/consumers of this
chain. They cannot become alternate epistemic persistence authorities.

## ProductRuntimeRunV1

`core.product_runtime_v1.converge_product_runtime_v1()` composes existing production
contracts. It does not clone their reducers or persistence logic.

For one exact `CaseLedgerBundle` it:

1. verifies the canonical ledger bundle;
2. rebuilds Epistemic v2 using an explicit `EpistemicPolicyV2`;
3. rebuilds the Evidence Trust Graph using an explicit `TrustPolicyV1`;
4. builds and offline-verifies Case Replay v2 using complete `RuntimeIdentity` and an
   explicit migration registry;
5. runs the existing deterministic `ReasoningEngine` for an explicit target artifact;
6. requires every reasoning `evidence_ref` to resolve to an exact EVENT or ASSERTION node
   in the exact Evidence Trust Graph;
7. emits a content-addressed `ProductRuntimeProofV1` binding all identities above.

A valid epistemic `ABSTAIN` is preserved as a first-class runtime outcome. PRC-01 never
promotes uncertainty to obtain PASS.

## ProductRuntimeProofV1 identity

The proof binds at least:

- exact `CaseId`;
- exact Canonical Ledger head;
- exact `CaseLedgerBundle` digest;
- exact Epistemic v2 projection identity;
- exact Evidence Trust Graph identity;
- exact Case Replay v2 manifest identity;
- exact Case Replay v2 bundle identity;
- exact RuntimeIdentity digest;
- explicit reasoning target;
- deterministic reasoning-result digest and outcome;
- exact trust-node identities used as reasoning evidence;
- proof schema and content-addressed proof identity.

Changing any bound semantic input creates a different proof identity.

## Reasoning evidence boundary

Legacy free-form evidence labels such as `DOC-1` or `DOC-1#p1` are not sufficient inside a
PRC-01 proof. A converged reasoning artifact must use exact Evidence Trust Graph node IDs,
for example:

- `event:sha256:<digest>`; or
- `assertion:sha256:<digest>`.

DECISION nodes are not accepted as reasoning evidence. Authorization and attestation remain
provenance/integrity evidence and never become epistemic truth merely by being present in the
graph.

## Existing release boundary

PRC-01 does not add a second publish/release gate.

The existing `authorize_cognitive_release()` remains the single cognitive document release
authorization boundary. An approved `DocumentBinding` must now contain exactly one
`product_runtime` input reference with:

- artifact id `case:<CaseId>`;
- artifact version `1`;
- digest equal to the `ProductRuntimeProofV1` content digest.

Missing, ambiguous, malformed or unsupported runtime binding fails closed. The existing
Decision/Strategy/ActionPlan/human-approval checks remain unchanged and cumulative.

## Fail-closed conditions

PRC-01 rejects, rather than guessing or truncating, at least:

- unsupported Product runtime proof schema;
- malformed content-address identity;
- cross-case proof substitution;
- stale or divergent CCL/replay/projection identity;
- replay tampering or incomplete RuntimeIdentity;
- reasoning result that is not reproducible from the exact artifacts and target;
- reasoning evidence reference absent from the exact trust graph;
- reasoning evidence reference pointing to a disallowed trust-node kind;
- missing/ambiguous/malformed Product runtime release binding.

Unknown future schemas/profiles require an explicit versioned migration/contract. They do not
receive implicit compatibility.

## Privacy boundary

PRC-01 changes no privacy rule. Real cases, source documents, PII, case numbers and private
runtime stores remain local-only under the documented `MVROS_DATA_ROOT` boundary. Public
GitHub and GitHub Actions use code and approved synthetic/non-sensitive fixtures only.

## Non-goals

PRC-01 does not:

- create or mutate CCL events;
- introduce a second database or graph store;
- persist Epistemic/Trust/Reasoning as a competing authority;
- change Gold/KQM certification state;
- claim independent review or certification;
- migrate real private cases into GitHub/CI;
- redesign the operator UX;
- implement PVE-01 real-case Product validation.

PVE-01 is intentionally subsequent: it measures this converged runtime on synthetic and
private local real-case vertical slices after PRC-01 engineering closure.

## Closure criteria

PRC-01 is `CLOSED / ENGINEERING PASS` only after:

- implementation exists;
- focused and adversarial tests pass;
- legacy release paths cannot bypass the Product runtime binding;
- full regression, Ruff and MyPy pass;
- security/policy/repository gates pass;
- all required workflows pass on one exact PR-head SHA;
- unchanged exact head is guarded-merged;
- resulting `main` completes terminal post-merge validation;
- immutable `v1.0.1` release/tag identity remains unchanged;
- exact closure evidence is recorded in canonical governance.

Engineering closure does not assert independent external certification.
