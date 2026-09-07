# LUKART ROS — Case Replay v2

Status: PHX-05 engineering contract
Authority: verification/projection only
Writable case SSOT: Canonical Case Ledger (CCL)

## Problem

A historical case result is not reproducible merely because source code or a rendered
report still exists. Exact replay requires the immutable case history and every identity
that can change the deterministic result to be explicit, content-addressed and checked
fail-closed.

## Decision

Case Replay v2 is a portable verification artifact over the existing trust chain. It is
not a database and it has no Product write authority.

Canonical replay chain:

`CCL bundle -> Epistemic v2 -> Evidence Trust Graph -> replay verification`

The replay manifest binds:

- exact `case_id` and CCL ledger head;
- exact content-addressed CCL bundle;
- Epistemic v2 projection identity and policy identity;
- Evidence Trust Graph identity and trust-policy identity;
- RuntimeIdentity v3 digest, including exact code/config/corpus/provider/plugin/input/
  evidence and execution-environment declarations;
- case schema version and the complete replay schema-identity set;
- deterministic migration-registry identity;
- evidence digests;
- content-addressed replay manifest identity.

The replay bundle embeds the canonical ledger bundle and canonical snapshots of the
runtime, migration registry and projection policies. Verification rebuilds Epistemic v2
and the Trust Graph from the embedded CCL history without database or provider access and
checks the rebuilt identities against the manifest.

## Identity semantics

`IDENTICAL` is permitted only when complete manifest identity is equal. Partial identity
must never be upgraded to `IDENTICAL`.

A different case is `DIFFERENT`.

A schema change can be `CROSS_VERSION_COMPARABLE` only when an explicit deterministic
migration path exists in the supplied migration registry and the candidate manifest is
bound to that exact registry identity. Unknown or ambiguous migration paths fail closed.

Changing code, configuration, corpus, provider/model identity, plugin inventory,
execution environment, evidence, CCL history, projection policy or projection result
creates a different replay identity.

## Migration contract

`CaseMigrationRegistry` owns one deterministic migration topology. Its canonical registry
identity is content-addressed. Migration implementation remains bound to the exact
RuntimeIdentity/code SHA; topology identity does not pretend that two different code
implementations are identical.

Unknown, missing, cyclic/ambiguous or non-deterministic migration behavior is a hard
failure. Historical evidence is never silently rewritten.

## Offline verification boundary

Offline verification means that the bundle can validate its embedded case history and
rebuild deterministic Product projections without live database, network provider or
model access. It does not claim that arbitrary provider/model executions can be rerun
without their separately captured deterministic artifacts and exact runtime environment.
Those identities remain explicit in RuntimeIdentity and any missing inventory is a hard
`INCOMPLETE`/failure boundary rather than an inferred equivalence.

## Security and trust invariants

- Canonical Case Ledger remains the only writable case-history SSOT.
- Replay has no CCL write API and no persistent truth store.
- Exact ledger head is mandatory for non-empty histories.
- Cross-case substitution fails closed.
- Tampered ledger, manifest, runtime, migration registry, epistemic policy or trust policy
  fails verification.
- Unknown replay schema or projection schema identity fails closed.
- Attestation/provenance evidence never automatically promotes epistemic truth.
- Recomputed output is a new identity; old published evidence remains immutable.
- Exact-SHA CI evidence is invalid after branch-head movement.

## Alternatives rejected

1. **Store rendered results as replay authority** — rejected because renderer output is a
   projection and cannot prove the underlying epistemic/provenance state.
2. **Second replay/event database** — rejected because it creates dual writable authority
   and unnecessary consistency failure modes.
3. **Provider/model-specific replay engine** — rejected because it breaks model/provider
   independence and cannot guarantee long-horizon reproducibility.
4. **Treat matching business output as IDENTICAL** — rejected because it hides changes in
   code, policy, evidence, configuration or runtime.

## Validation requirements

Closure requires focused, adversarial and full regression validation plus exact candidate
SHA CI, guarded exact-head merge and post-merge validation. Required negative cases include
at least tampered ledger history, wrong case/head, incomplete runtime identity, altered
policy/registry identity, unknown migration and cross-case comparison.

External independent certification is not implied by engineering PASS.
