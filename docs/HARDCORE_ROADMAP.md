# LUKART ROS — Hardcore Enterprise Roadmap H1-H10

Status: Active development roadmap
Historical release authority: live annotated Git tag `v1.0.1`; H1 validates both the tag-object identity and its target commit, and development work MUST NOT move or reinterpret either identity.
Predecessor: Enterprise E0-E10 engineering implementation. E10 remains capped at `INDEPENDENT_REVIEW_REQUIRED` unless genuine separately attested independent review evidence exists.

This roadmap extends existing P2/P3/Enterprise authorities. It MUST NOT create a parallel reasoning, epistemic, provider, replay, authorization, provenance or certification authority where a canonical mechanism already exists.

## H1 — Exact-SHA Evidence Integrity & Baseline Reconciliation

Failure mode: validation can be green on a PR head while the merge SHA is never subjected to the Enterprise gate, and static governance documents/configuration can drift from the immutable release tag or confuse an annotated tag object's identity with its target commit.

Controls:
- bind the Enterprise gate to the exact checked-out candidate SHA;
- validate the configured historical `v1.0.1` target commit and annotated tag-object SHA against live Git;
- fail closed on baseline drift in canonical governance documents;
- run the Enterprise gate on both PR candidates and post-merge `main`;
- fetch sufficient Git history/tags for historical baseline validation;
- emit deterministic H1 evidence containing candidate identity, both historical release identities and digests of canonical baseline documents/workflow.

Acceptance:
- wrong candidate SHA, moved/wrong historical release identity, stale canonical baseline text, missing post-merge gate or insufficient tag history all fail closed;
- PR head and resulting `main` merge SHA each receive their own validation evidence;
- no historical release/tag mutation occurs.

## H2 — Repository Policy & Required-Check Drift Enforcement

Failure mode: code-level gates can exist while repository rulesets/required-check policy is absent, stale or bypassable.

Controls:
- inventory effective branch/ruleset policy;
- bind required contexts to canonical workflow/job identities;
- detect policy drift and missing required checks;
- document authorized bypass paths and deny undeclared bypass assumptions.

Acceptance: merge policy is machine-auditable and a missing required trust/security gate cannot silently become mergeable policy.

## H3 — Supply-Chain Provenance Closure

Failure mode: pinned Actions and an SBOM do not by themselves bind every produced artifact to the exact source/dependency/build identity.

Controls:
- extend existing E4 SBOM/provenance rather than creating a second format;
- bind build artifacts to source SHA, dependency identity, workflow identity and builder context;
- verify provenance/material consistency and dependency-boundary policy;
- preserve full-SHA Action pinning and least privilege.

Acceptance: missing/mismatched material identity, unpinned workflow dependency or provenance inconsistency fails closed.

## H4 — Execution Boundary & Capability Isolation

Failure mode: process isolation can be mistaken for a stronger kernel/container sandbox and capability leakage may cross the worker boundary.

Controls:
- strengthen the existing E2 worker boundary with explicit filesystem/network/process/resource capability policy;
- preserve timeout/cancellation/bounded execution;
- record which isolation controls were actually enforced;
- add OS/container isolation only where justified and actually enforced.

Acceptance: denied capability use, inherited secret/environment leakage and boundary misrepresentation are adversarially rejected.

## H5 — Deterministic Replay Identity & Migration Closure

Failure mode: replay/migration results can look equivalent while code/config/corpus/schema/provider/plugin/input identities differ.

Controls:
- extend canonical P2/P3 replay/migration identity;
- bind code SHA, config digest, corpus digest, schema version, provider/plugin versions and input/evidence digests;
- distinguish identical replay from comparable cross-version replay;
- fail closed on unknown migration paths/versions.

Acceptance: incomplete replay identity can never be labeled identical replay, and semantic divergence remains visible.

## H6 — Tenant/Case Isolation & Authorization Adversarial Closure

Failure mode: valid RBAC rules may still permit confused-deputy, cross-case or cross-tenant paths through composition.

Controls:
- extend E5 authorization receipts and deny-by-default policy;
- adversarially test tenant, case, workspace, role, scope and trust-promotion boundaries;
- bind authorization decisions to request/resource identity and replay protections.

Acceptance: undeclared cross-boundary access or promotion is rejected with deterministic auditable evidence.

## H7 — Recovery, Rollback & Failure-Containment Closure

Failure mode: a system can survive nominal tests yet fail during partial writes, crashes, restore, rollback or promoted-change recovery.

Controls:
- extend E6 durability and E9 resilience matrices;
- test crash consistency, corruption, partial persistence, backup/restore and rollback;
- verify restored/replayed semantic and provenance identity;
- bound blast radius of recovery actions.

Acceptance: recovery produces verified state or explicit failure; silent partial recovery is impossible.

## H8 — Scale, Concurrency & Resource-Budget Closure

Failure mode: bounded primitives can still exhibit nondeterminism, excessive memory/runtime or unbounded graph/replay propagation at realistic scale.

Controls:
- measure small/medium/large/stress profiles;
- profile runtime, memory, concurrency, cache behavior, replay and graph propagation;
- use deterministic structural assertions where wall-clock thresholds would be brittle;
- enforce explicit concurrency/resource budgets.

Acceptance: resource-limit breach or nondeterministic work identity is visible and blocks the applicable gate.

## H9 — Tamper-Evident Audit & Operational Evidence Closure

Failure mode: component-level logs/telemetry can be incomplete, mutable or insufficient for incident reconstruction.

Controls:
- extend E6/E7 provenance and observability into a bounded evidence bundle;
- correlate run/case/provider/workflow identities;
- preserve PII redaction and least-data telemetry;
- detect tampering, gaps and incompatible schema versions.

Acceptance: an operator can reconstruct the validated control path without chat history, and missing/tampered audit evidence remains explicit.

## H10 — Hardcore Engineering Evidence Closure

Failure mode: results from different commits or incomplete stages can be combined into a misleading final PASS/certification claim.

Controls:
- aggregate H1-H9 evidence for one exact candidate SHA and canonical configuration identity;
- reject mixed-SHA, missing-stage, failed-stage or unverifiable evidence;
- generate a replayable evidence manifest/bundle;
- keep independent review/certification outside automated authority.

Acceptance: automation may establish Hardcore engineering evidence completeness, but absent genuine independent evidence the final state remains `INDEPENDENT_REVIEW_REQUIRED`.

## Definition of Done

A stage is complete only after implementation, focused tests, adversarial tests, full regression, lint, type-check, applicable security/policy gates, exact-SHA CI, validated PR-head merge, post-merge `main` validation and preserved historical release identity. A branch, commit, PR or partial green CI is not completion.
