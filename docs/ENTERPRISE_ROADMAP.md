# LUKART ROS — Enterprise Hardcore Track

Status: Active engineering hardening program
Baseline: `main @ 8550d08651957afd7f21b91553768786cb8bcf6e`
Immutable historical release: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`

## Purpose

The Enterprise Track hardens the already-working LUKART ROS product without creating a second
reasoning or epistemic authority. Existing P2/P3 semantics remain authoritative. Enterprise
components protect execution, trust, persistence, interoperability, operations and release
governance around that core.

The fixed execution order is E0 through E10. A later stage may strengthen an earlier control,
but may not bypass or weaken it.

## Enterprise invariants

1. Evidence and epistemic state remain Product authorities; infrastructure cannot manufacture FACT.
2. Trust is fail-closed and cryptographically bound where external trust is transferred.
3. Agents and plugins are untrusted workers; their outputs require normal Product validation.
4. Historical Gold/release artifacts are immutable.
5. Every trusted artifact is reproducible from exact code/config/corpus/schema/provider identities.
6. Security claims must describe the actually enforced boundary; no thread/process control is called
   an OS sandbox unless the OS enforces it.
7. Every state mutation is attributable, auditable, bounded and reversible where reversal is valid.
8. Missing security/certification evidence is FAIL or INCOMPLETE, never implicit PASS.
9. Enterprise engineering PASS is distinct from independent analytical/security certification.

## E0 — Governance Reset & Release Hygiene

- Enterprise roadmap and machine-readable policy become current governance targets.
- Development version is separated from immutable v1.0.1 release identity.
- Existing v1 release workflow skips already-published historical versions instead of generating
  misleading failures on later development SHAs.
- Enterprise checks are composed into an already-required Stage Gate so ruleset coverage cannot be
  accidentally omitted while repository-administration APIs are unavailable.
- SECURITY.md and CODEOWNERS are present.

Acceptance: governance is internally consistent; v1.0.1 tag is never moved; development commits do
not attempt to republish v1.0.1.

## E1 — Enterprise Threat Model & Trust Architecture

- explicit trust zones, actor capabilities, assets, threats and invariants;
- data classification and authorization context;
- deny-by-default cross-zone transitions;
- critical threats require explicit mitigations and evidence identifiers.

Acceptance: unknown zone/permission/classification fails closed and threat coverage is measurable.

## E2 — Process Isolation Boundary

- agent/plugin execution can run in a separate spawned process;
- hard wall-clock termination and process kill;
- POSIX CPU/address-space limits when the host supports them;
- sanitized environment and temporary working directory;
- Python-runtime network guard when network capability is denied;
- isolation report states exactly which controls were actually enforced.

Acceptance: timeout kills the worker, environment secrets are not inherited, denied Python socket
access fails, and no result is trusted merely because it came from the worker.

## E3 — Cryptographic Trust & Signed Attestations

- Ed25519 signatures over canonical attestations;
- key identifiers, issued/expiry timestamps, purpose, subject digest and payload digest;
- verifier allow-list and key revocation;
- replay/KQM/release/API trust can require a valid attestation;
- private keys are never stored in repository artifacts.

Acceptance: tamper, wrong key, expired/revoked key, wrong purpose and wrong subject all fail closed.

## E4 — Software Supply Chain Security

- deterministic CycloneDX SBOM generation from declared project dependencies;
- GitHub Actions pin audit requiring full 40-character commit SHAs;
- dependency declarations and workflow references are machine-auditable;
- SLSA-style provenance subject/material model is represented in evidence bundles;
- security workflow supports static/security scanning without granting write permissions.

Acceptance: unpinned actions or malformed dependency/SBOM/provenance data fail the enterprise gate.

## E5 — Identity, Authorization & Data Isolation

- RBAC + attribute checks around case/tenant/workspace access;
- least privilege and deny-by-default;
- confidential/restricted data cannot cross tenant boundaries;
- authorization decisions produce deterministic audit receipts;
- trust promotion permission is separate from read/write permissions.

Acceptance: cross-tenant, missing-role, missing-scope and unauthorized promotion paths are rejected.

## E6 — Durable Provenance, Backup & Recovery

- SQLite transactional hash-chain ledger with WAL and FULL synchronous mode;
- monotonic sequence and content-addressed records;
- integrity verification on read/append;
- verified online snapshot/backup and restore drill;
- restored head digest must equal source head digest.

Acceptance: corruption, discontinuity and invalid restore all fail closed.

## E7 — Enterprise Observability & SRE Boundary

- structured trace/metric/event contracts;
- correlation identifiers for case/run/provider;
- PII redaction before telemetry leaves the component;
- bounded telemetry attributes and cardinality;
- SLI/SLO evaluation for latency/error/saturation indicators;
- OpenTelemetry-compatible semantic boundary without making telemetry a Product authority.

Acceptance: secrets/PII are redacted and missing SLI evidence cannot become SLO PASS.

## E8 — Stable Enterprise API Guard

- versioned request contracts on top of P3 digest-bound API;
- authorization context, nonce/replay protection and idempotency keys;
- payload limits, rate quotas and deterministic receipts;
- trusted analytical state requires valid cryptographic authorization/attestation;
- unknown contract/version fails closed.

Acceptance: replay, quota overflow, payload overflow, tenant mismatch and forged trust are rejected.

## E9 — Resilience / Chaos / Fuzz / Scale

- deterministic failure scenarios for corruption, timeout, cancellation, duplicate requests and
  provider failure;
- bounded synthetic scale profiles up to large evidence/graph sizes outside the normal PR fast path;
- structural correctness after injected failures is measured, not inferred from lack of exceptions;
- recovery and semantic integrity remain visible metrics.

Acceptance: every critical failure class has an executable negative test and deterministic evidence.

## E10 — Enterprise Certification Gate

The gate consumes evidence from E0-E9. It can return:

- `ENGINEERING_PASS` — automated controls passed on one exact SHA;
- `INCOMPLETE` — required evidence missing;
- `FAIL` — a control failed;
- `INDEPENDENT_REVIEW_REQUIRED` — engineering evidence is complete but human/security review is
  still required for Enterprise Candidate status.

The automated gate MUST NOT self-declare independent review or external certification.

## Definition of Done

E0-E10 are engineering-complete only when Ruff, MyPy, focused enterprise/adversarial tests, P2/P3
compatibility tests, full regression, Stage Gate and the dedicated Enterprise workflow all pass on
one exact PR head SHA. Merge must use that exact SHA.

A merged engineering implementation is not, by itself, an independently certified Enterprise
release.