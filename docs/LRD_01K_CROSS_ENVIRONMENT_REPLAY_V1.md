# LRD-01K — Cross-Environment Replay & Environment Provenance v1

Status: IMPLEMENTATION / VALIDATION IN PROGRESS. This document is a stage contract and evidence map only. The sole engineering-process authority remains `docs/WORKING_PRINCIPLES.md`.

## Problem and authority boundary

LRD-01I preserves a provider-neutral offline survivability package but intentionally requires a compatible Python bootstrap and does not prove universal future-platform execution. LRD-01K measures whether preserved replay material remains verifiable across materially different execution environments without calling those environments identical.

LRD-01K is verification-only. It does not create Product, Canonical Case Ledger, Gold, policy, trust-root, release, dependency, migration, crypto, or semantic-comparison authority. LRD-01D remains the semantic drift authority. SSC-02 remains dependency/build-material authority. LRD-01I remains the preserved survivability-bundle authority. CASE-OPS-07 environment-bound OCR semantics are not upgraded by 01K.

## Evidence model

`ExecutionEnvironmentProfileV1` is the immutable declared environment contract. Required compatibility includes OS family, CPU architecture, Python implementation/version/cache tag/SOABI, dependency lock identity, physical dependency-artifact identities, canonicalization identity, migration-registry identity, crypto-profile identity, exact LRD-01I bundle identity, verifier identity, and environment-policy identity. OpenSSL, SQLite, libc/runtime, filesystem behavior and related runtime details are observed provenance. Locale and timezone are recorded but treated as non-semantic unless an upstream authority declares otherwise.

`ObservedEnvironmentReceiptV1` is collected during execution. It records actual OS/runtime, architecture, Python/ABI, OpenSSL, SQLite, libc/runtime, locale, timezone, filesystem semantics, and a physical installed-artifact inventory digest derived from installed file bytes. A CI label such as `ubuntu-latest` is never used as evidence authority.

`CrossEnvironmentReplayPlanV1` binds the exact LRD-01I bundle, SSC-02 identity, environment-profile matrix, LRD-01D comparison policy binding, migration/canonicalization/crypto identities and hard bounds. `CrossEnvironmentReplayReceiptV1` binds one actual execution to its declared and observed environments, semantic identity, invariant evidence and failure state. `CrossEnvironmentReplayReportV1` aggregates a complete matrix and is content-addressed; a later drill creates a new report and may use `supersedes` rather than rewriting historical evidence.

## Result semantics

01K maps evidence from LRD-01D; it does not recompute semantic equality. `NO_DRIFT` maps to `EXACT_ENVIRONMENT_REPLAY` only when the environment profile equals the plan reference profile, otherwise to `CROSS_ENV_SEMANTICALLY_EQUIVALENT`. `PRESENTATION_ONLY` maps to `PRESENTATION_ONLY_DRIFT`; `SEMANTIC_DRIFT` maps to `SEMANTIC_DRIFT`; incomplete/abstained evidence maps to `UNVERIFIABLE`; incompatible required environment fields map to `ENVIRONMENT_INCOMPATIBLE`.

## Offline and least privilege

Replay evidence declares network `DENY`, no CCL/Product writes, no Gold/policy/trust-root/release/tag authority and no cloud/AWS credentials. The standalone aggregate verifier is Python-stdlib-only and validates strict schemas, outer and inner content identities, exact field-class mapping, matrix completeness, provenance references, physical installed-artifact binding, LRD-01I/SSC-02/policy/migration/canonicalization/crypto bindings, compatibility, LRD-01D-to-01K classification consistency, statuses, and least-privilege fields before accepting the report.

The native migration path uses current supported Python environments while preserving exact identity bindings. The second path is a content-addressed OCI Image Layout containing the standalone verifier. CI executes the verifier inside a container with `--network none` and separately verifies OCI blob identities. OCI is not a permanent machine: compatible host kernel/container runtime/CPU remain external dependencies, and mutable image tags are never identity authority.

## CI matrix and nondeterminism

The security-critical CI matrix targets the repository-supported Python range with three actual profiles: Linux x86-64 / Python 3.11, Linux x86-64 / Python 3.14, and Windows x86-64 / Python 3.14. Every matrix leg captures actual observed provenance after frozen dependency installation. Aggregate verification rejects missing, duplicated or swapped profiles/receipts.

Focused/adversarial tests cover strict schemas, unknown classifications, OS/CPU/Python ABI mismatch, physical dependency inventory substitution, LRD-01I/migration/canonicalization/crypto substitution, exact field-class reassignment, partial matrix, duplicate/cross-environment receipt errors, forged recomputed classifications, pinned-outer-digest tampering, OCI blob substitution and exact-vs-cross-environment classification. CI additionally runs LRD-01D, LRD-01I, SSC-02, LRD-01J, Case Replay v2 and CASE-OPS-07 regressions. `PYTHONHASHSEED` and `SOURCE_DATE_EPOCH` are pinned in CI; locale/timezone/path/filesystem remain observed provenance and are exercised by the operator drill before closure.

## Closure boundary

GitHub CI evidence is synthetic/public and contains no private case material. It proves the contracts and actual GitHub-hosted environment matrix, not the user's local workstation. LRD-01K must not be declared CLOSED until a real operator drill has also executed the same candidate on the approved local Windows + WSL profiles and its receipts are validated. If direct access to that machine is unavailable in the engineering session, that is a real evidence blocker, not a reason to manufacture PASS.

AWS/provider durability remains outside 01K and deferred according to the live roadmap. No AWS/provider PASS is claimed here.
