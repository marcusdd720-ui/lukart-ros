# KQM-03 — Identity-Preserving Longitudinal KQM v1

Status: `IMPLEMENTATION / VALIDATION PENDING`

## Problem

PHX-02 already binds immutable Gold source/content identity, KQM policy identity,
evaluator identity, evaluation purpose/splits and exact per-case Canonical Case Ledger
heads into `EvaluationInputIdentity`. `KQMProjection` is a deterministic measurement
artifact over that exact input.

The older P3 longitudinal quality store predates PHX-02. Its historical point contract
contains only `release_id`, `code_sha`, `corpus_digest` and metrics. That representation
cannot prove that two persisted measurements used the same KQM policy, evaluator or exact
CCL heads. Treating such points as directly comparable would therefore overstate evidence.

## Decision

KQM-03 adds a separately versioned longitudinal measurement contract over PHX-02 rather
than weakening or rewriting the legacy P3 store.

A `KQMLongitudinalPoint` binds:

- exact PHX-02 `EvaluationInputIdentity` as the comparison context;
- exact corpus, policy and evaluator identities;
- exact candidate `RuntimeIdentity` digest;
- exact `KQMProjection` identity;
- measured metrics and the projection PASS/failure set;
- a content-addressed point identity.

The candidate runtime is deliberately outside the comparison-context identity. Product
or candidate code is expected to change between measurements; benchmark/evaluation
context is not. Candidate runtime must be complete for replay before a longitudinal point
can be created.

## Comparability rule

Two KQM points are comparable only when all of the following remain exact and identical:

1. `EvaluationInputIdentity`;
2. KQM policy identity;
3. evaluator identity;
4. corpus identity.

Because `EvaluationInputIdentity` already binds purpose, split membership, exact selected
case IDs and exact CCL heads, any change to those inputs creates a new context and the
comparison fails closed.

A candidate runtime change alone does not invalidate comparability; it creates a new point
identity and is the intended subject of longitudinal measurement.

## Metric semantics

KQM-03 reuses the existing KQM v2 `MetricDirection` definitions. It does not introduce
new thresholds or silently reinterpret metrics.

For an unchanged comparison context:

- `MIN`: higher values are improvement, lower values are regression;
- `MAX`: lower values are improvement, higher values are regression;
- unchanged values are `STABLE`;
- a metric absent from either side is `MISSING` and the comparison is not regression-free;
- unexpected metrics fail the comparison contract.

The resulting comparison is content-addressed and bound to both exact point identities.
`regression_free` is derived only from the delta set and is not release authorization.

## Persistence

`PersistentKQMHistory` reuses the existing P3 append-only hash-chain provenance ledger.
A history instance is bound to one exact evaluation context and one exact policy identity.
It rejects context substitution, policy substitution and duplicate release IDs. Tampering
is detected by the existing provenance hash chain before points are accepted.

This store is measurement history only. It is not the Canonical Case Ledger and cannot
create or modify Product truth.

## Trust boundaries

KQM-03:

- has no Canonical Case Ledger write path;
- cannot mutate Gold or locked evaluation inputs;
- cannot change KQM policy thresholds;
- cannot promote epistemic state;
- cannot authorize a Product or release;
- cannot claim human, independent, external or security certification;
- does not reinterpret historical P3 points as PHX-02-equivalent evidence.

Legacy P3 longitudinal records remain valid historical artifacts at their original trust
level. They are not silently upgraded to KQM-03 points because the missing identity fields
cannot be reconstructed without evidence.

## Validation requirements

Closure requires one exact PR-head SHA to pass:

- focused point/comparison identity tests;
- adversarial context-substitution, missing-metric and incomplete-runtime tests;
- persistent round-trip, duplicate-release and tamper tests;
- Ruff and MyPy;
- full pytest regression;
- Stage Gate and repository security/policy workflows;
- guarded exact-head merge;
- resulting-main post-merge validation;
- immutable `v1.0.1` baseline/release side-effect check.

Engineering PASS does not imply independent certification.
