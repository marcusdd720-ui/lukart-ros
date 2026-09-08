# PVE-01 — Product Verification Evidence v1

Status: `IMPLEMENTATION / VALIDATION PENDING`
Authority: measurement-only derived evidence
Depends on: `PRC-01 CLOSED / ENGINEERING PASS`
Canonical Product history authority: Canonical Case Ledger (CCL)

## Problem

PRC-01 converged the Product runtime into one proof-bound chain, but implementation existence
is not evidence that the chain behaves correctly across supported, abstaining and adversarial
vertical slices. PVE-01 adds a small reproducible verification boundary over exact PRC runtime
artifacts.

PVE-01 does not create a truth store, Gold authority, certification authority or private-case
upload path. It measures already-built Product runtime results.

## Architectural decision

`core/product_verification_evidence_v1.py` is verification/measurement-only. It consumes
`ProductRuntimeRunV1` values and delegates Product semantics to their existing `verify()`
contracts.

Authority remains:

`Evidence -> CCL -> Epistemic v2 -> Trust Graph -> Reasoning -> Result -> Replay -> ProductRuntimeProofV1`

PVE-01 sits outside this chain and produces content-addressed measurement evidence only.

## Fixed PVE-01 registry

A caller cannot omit difficult scenarios and still construct a PVE-01 PASS report. The v1
registry contains exactly five checks:

1. `SUPPORTED_CONCLUSION` — a fully supported exact Product runtime chain concludes and
   remains verifiable.
2. `ABSTAIN_OPEN_QUESTIONS` — unresolved support produces deterministic `ABSTAIN` and keeps
   explicit open questions visible.
3. `TAMPER_REJECTION` — a content-address-consistent proof whose reasoning-result digest is
   substituted is rejected by the production PRC verifier.
4. `CROSS_CASE_REJECTION` — a content-address-consistent proof substituted into another case
   is rejected by the production PRC verifier.
5. `EVIDENCE_DETERMINISM` — repeated verification of exact inputs produces identical evidence
   identities.

The registry itself is content-addressed. Changing the set or semantics requires a new
versioned contract.

## Exact identity binding

`verify_product_evidence_v1()` requires both `code_sha` and `expected_code_sha`. Verification
fails before measurement unless both are canonical lowercase Git object IDs and exactly
equal.

The final report binds:

- exact code SHA;
- exact PVE registry identity;
- exact supported PRC proof identity;
- exact abstaining PRC proof identity;
- each required check result identity;
- each check evidence identity;
- report schema and PASS outcome.

Each PRC run evidence also binds its exact case ID, CCL head, RuntimeIdentity digest, replay
manifest/bundle identities, reasoning-result digest/outcome and Product runtime proof
identity.

## Epistemic safety

`ABSTAIN` is a successful PVE measurement when the underlying Product runtime correctly
refuses to conclude. Open questions are preserved in the measurement evidence. PVE-01 does
not reinterpret an abstention as a FACT or conclusion.

Likewise, rejection of tampering or cross-case substitution is a successful security/trust
measurement, not a Product truth assertion.

## Privacy boundary

Public CI uses synthetic/non-sensitive fixtures only. Real case documents, PII, case numbers
and private runtime stores remain under the local `MVROS_DATA_ROOT` boundary and must not be
uploaded to GitHub or GitHub Actions.

A future local real-case PVE observation may be reported only from separately available local
evidence. Repository automation cannot fabricate that evidence or promote an unavailable
private-case run into PASS.

## Fail-closed conditions

PVE-01 aborts without a PASS report when, among other conditions:

- code SHA binding is malformed or stale;
- a supplied PRC run does not verify;
- the supported scenario does not `CONCLUDE`;
- the abstention scenario does not `ABSTAIN` or exposes no open question;
- tampered reasoning identity is accepted;
- cross-case proof substitution is accepted;
- repeated evidence identity diverges;
- registry/result/report content identity is malformed;
- any required check is missing, duplicated or reordered.

There is no partial PVE-01 PASS report.

## Non-goals

PVE-01 does not:

- write CCL events;
- persist Product truth or verification state;
- modify Epistemic/Trust/Reasoning semantics;
- freeze or modify Gold/KQM;
- certify private real-case quality without actual local evidence;
- claim independent analytical/security review;
- replace later KQM-03 or governance stages.

## Closure criteria

PVE-01 becomes `CLOSED / ENGINEERING PASS` only after:

- fixed registry and content-addressed evidence/report implementation exist;
- focused and adversarial tests pass;
- full regression, Ruff and MyPy pass;
- security/privacy/policy gates pass;
- all required workflows pass on one exact PR-head SHA;
- unchanged exact head is guarded-merged;
- resulting `main` completes terminal post-merge validation;
- historical `v1.0.1` release/tag identity remains unchanged;
- canonical governance records exact closure evidence.

Engineering closure does not assert independent external certification or unavailable
private-case verification.
