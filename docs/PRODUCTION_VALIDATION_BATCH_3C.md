# Production Validation — Batch 3C

Status: **IMPLEMENTED / final PR-head validation required before merge**

Scope: Production Validation Step 12 (`Controlled Learning experiments`) and Step 15
(`Local private-case pilot`).

## Step 12 — Controlled Learning experiments

Implementation status: **IMPLEMENTED; synthetic controlled-path validation available**.

The Step 12 harness reuses the existing P4-P7 control path instead of introducing a second
learning authority:

`MeasuredFailure -> AdversarialVerificationGate -> Semantic diagnosis -> LearningCandidate -> Experiment -> PromotionGate -> fresh-SHA replay/KQM evidence -> SemanticSelfHealingGate -> ControlledSelfLearningGate`

The harness verifies the registry-required properties:

- `measured_failure_bound`;
- `candidate_experiment_executed`;
- `promotion_gate_applied`;
- `production_mutation_absent`.

Additional invariants:

- only `development` / `validation` experiment inputs are allowed;
- locked evaluation is not used for tuning;
- private Case data is not used;
- the harness creates no Product mutation, deployment, merge, or certification authority;
- baseline and candidate revisions must be different full Git SHAs;
- measured regression is fail-closed: the existing P4 PromotionGate rejects the candidate and
  P7 returns `SUSPENDED`, preserving the canonical self-learning safety semantics.

The first Batch 3C code head exposed one incorrect test expectation: the test expected
`REJECTED` after a measured guardrail regression, while the canonical P7 contract intentionally
returns `SUSPENDED`. The repair changed only the test expectation and did not weaken or alter the
P4/P6/P7 implementation.

A fresh repaired code head passed CI Foundation on Python 3.11, 3.12, and 3.13 before this
SSoT record was added. Because this documentation changes the branch SHA, the final PR head must
again pass the complete fresh-SHA validation sequence before merge.

## Step 15 — Local private-case pilot

Implementation status: **IMPLEMENTED / REAL LOCAL PILOT NOT YET EXECUTED**.

The public repository contains only the pilot contract, tests, and operator command. Real Case
content, paths, evidence, and pilot output remain outside the repository.

`prepare_local_private_pilot(...)` is deliberately non-claiming. Preparation alone sets no
privacy or execution check to PASS and cannot satisfy Step 15.

A real local pilot must use the operator command against an external private data root. The
runner:

1. validates that the private data root is outside the Git repository;
2. opens the existing local Case workspace and runs the existing Case pipeline;
3. binds the run to the current Git SHA;
4. records only a privacy-safe local result and SHA-256 fingerprints;
5. executes the repository PII/confidentiality scan;
6. checks tracked `cases/` files for prohibited private Case material;
7. creates a local-only attestation outside the repository.

The Step 15 attestation exposes only non-sensitive metadata and digests. It does not expose the
Case key, private data-root path, result path, or private result contents.

Full Step 15 PASS requires all registry checks from a real execution:

- `local_only_execution_attested`;
- `pii_not_committed`;
- `private_evidence_not_committed`;
- `pilot_results_recorded`.

Therefore Step 15 must not be reported as production PASS until a real private Case is executed
locally and its local attestation proves those four checks.

## Deliberate non-claims

Batch 3C does **not**:

- execute or expose a real private Case in GitHub CI;
- use locked evaluation for learning or tuning;
- authorize automatic Product mutation;
- certify production reasoning quality;
- bypass Step 1 or Step 5 independent external-review gates;
- authorize Step 20 release before the complete Production Validation chain is satisfied.

## Validation rule

The merge rule remains:

`FAIL -> diagnose -> smallest justified repair -> fresh SHA -> full CI/Audit/Smoke/Stage validation -> merge exact validated head -> post-merge validation`

No historical PASS from an earlier branch SHA authorizes merge of a later SHA.
