# LRD-01K — Cross-Environment Replay & Environment Provenance v1

Status: **CLOSED / ENGINEERING PASS**. This document is a stage contract and evidence map only. The sole engineering-process authority remains `docs/WORKING_PRINCIPLES.md`.

## Problem and authority boundary

LRD-01I preserves a provider-neutral offline survivability package but intentionally requires a compatible Python bootstrap and does not prove universal future-platform execution. LRD-01K measures whether preserved replay material remains verifiable across materially different execution environments without calling those environments identical.

LRD-01K is verification-only. It does not create Product, Canonical Case Ledger, Gold, policy, trust-root, release, dependency, migration, crypto, or semantic-comparison authority. LRD-01D remains the semantic drift authority. SSC-02 remains dependency/build-material authority. LRD-01I remains the preserved survivability-bundle authority. CASE-OPS-07 environment-bound OCR semantics are not upgraded by 01K.

## Evidence model

`ExecutionEnvironmentProfileV1` is the immutable declared environment contract. Required compatibility includes OS family, CPU architecture, Python implementation/version/cache tag/SOABI, dependency lock identity, physical dependency-artifact identities, canonicalization identity, migration-registry identity, crypto-profile identity, exact LRD-01I bundle identity, verifier identity, and environment-policy identity. Repository-source identities for the dependency lock and standalone verifier are SHA-256 digests of their exact Git blob bytes for the checked-out candidate, so platform checkout line-ending conversion cannot create a false identity change. Physical installed-artifact identities remain hashes of the actual runtime file bytes.

`ObservedEnvironmentReceiptV1` is collected during execution. It records actual OS/runtime, architecture, Python/ABI, OpenSSL, SQLite, libc/runtime, locale, timezone, filesystem semantics, and a physical installed-artifact inventory digest derived from installed file bytes. A CI label such as `ubuntu-latest` is never used as evidence authority.

`CrossEnvironmentReplayPlanV1` binds the exact LRD-01I bundle, SSC-02 identity, environment-profile matrix, LRD-01D comparison policy binding, migration/canonicalization/crypto identities and hard bounds. `CrossEnvironmentReplayReceiptV1` binds one actual execution to its declared and observed environments, semantic identity, invariant evidence and failure state. `CrossEnvironmentReplayReportV1` aggregates a complete matrix and is content-addressed; a later drill creates a new report and may use `supersedes` rather than rewriting historical evidence.

## Result semantics

01K maps evidence from LRD-01D; it does not recompute semantic equality. `NO_DRIFT` maps to `EXACT_ENVIRONMENT_REPLAY` only when the environment profile equals the plan reference profile, otherwise to `CROSS_ENV_SEMANTICALLY_EQUIVALENT`. `PRESENTATION_ONLY` maps to `PRESENTATION_ONLY_DRIFT`; `SEMANTIC_DRIFT` maps to `SEMANTIC_DRIFT`; incomplete/abstained evidence maps to `UNVERIFIABLE`; incompatible required environment fields map to `ENVIRONMENT_INCOMPATIBLE`.

## Offline and least privilege

Replay evidence declares network `DENY`, no CCL/Product writes, no Gold/policy/trust-root/release/tag authority and no cloud/AWS credentials. The standalone aggregate verifier is Python-stdlib-only and validates strict schemas, outer and inner content identities, exact field-class mapping, matrix completeness, provenance references, physical installed-artifact binding, LRD-01I/SSC-02/policy/migration/canonicalization/crypto bindings, compatibility, LRD-01D-to-01K classification consistency, statuses, and least-privilege fields before accepting the report.

The native migration path uses current supported Python environments while preserving exact identity bindings. The second path is a content-addressed OCI Image Layout containing the standalone verifier. CI executes the verifier inside a container with `--network none` and separately verifies OCI blob identities. OCI is not a permanent machine: compatible host kernel/container runtime/CPU remain external dependencies, and mutable image tags are never identity authority.

## CI matrix and nondeterminism

The security-critical CI matrix targets the repository-supported Python range with three actual profiles: Linux x86-64 / Python 3.11, Linux x86-64 / Python 3.14, and Windows x86-64 / Python 3.14. Every matrix leg captures actual observed provenance after frozen dependency installation. Aggregate verification rejects missing, duplicated or swapped profiles/receipts.

Focused/adversarial tests cover strict schemas, unknown classifications, OS/CPU/Python ABI mismatch, physical dependency inventory substitution, LRD-01I/migration/canonicalization/crypto substitution, exact field-class reassignment, partial matrix, duplicate/cross-environment receipt errors, forged recomputed classifications, pinned-outer-digest tampering, OCI blob substitution and exact-vs-cross-environment classification. CI additionally runs LRD-01D, LRD-01I, SSC-02, LRD-01J, Case Replay v2 and CASE-OPS-07 regressions. `PYTHONHASHSEED` is pinned in CI; locale/timezone/path/filesystem remain observed provenance and were exercised by the operator drill before closure.

## Canonical closure evidence

Implementation PR #230 was qualified on exact head SHA `395c9956bfae5d090e9c2c4a7aad844640fd069e` and merged to resulting main `5f6a72fd1e0dec6e84e306bbde66ac0614dd06c7`. The resulting main independently completed the full push-triggered validation set successfully before the operator drill.

The required real operator drill then executed the same candidate SHA on the approved local profiles:

- Windows x86-64, Python 3.14.7, `uv` 0.12.10;
- WSL2 / Ubuntu 26.04 LTS x86-64, Python 3.14.4, `uv` 0.12.10.

Both environments verified exact candidate SHA before evidence capture. The operator generated `windows-py314.json` and `wsl-py314.json`, aggregated them into `operator-report.json`, and ran the standalone LRD-01K verifier successfully. The verifier returned report digest:

`90fed6b18b0d9ac86752269887203aa1ffb81032181bcf5945c521fcbc76e2a5`

Operator-side SHA-256 evidence:

- `windows-py314.json`: `cf63dca4e43005a7407f201fb40ea694799ffbac0ac59f99858621b2e61510cd`;
- `wsl-py314.json`: `7e41323a296706422a41569ed6ffb55d6a063290f6343944c420590a343d8387`;
- `operator-report.json`: `2d1197e30a7097e976cee37ed83c81f763921a3793335b4bda013931f8db5b81`.

The operator report and receipts remain operator-hosted evidence; only their identities and observed validation result are recorded here. No private case material is added to the repository.

## Closure boundary and non-claims

The required local Windows + WSL operator evidence exists and its aggregate report was validated. This closes the LRD-01K engineering scope defined by this document.

Windows and WSL ran on the same physical computer. This stage therefore does **not** claim physical-media separation, geographic redundancy, real disaster-recovery execution, provider durability, key custody, independent/human/security review, bare-metal portability, macOS portability, ARM64 portability, universal future-platform execution, or elapsed real-world 10+ year survivability. OCI remains a frozen execution capsule with host kernel/runtime/CPU dependencies, not an eternal machine.

AWS/provider durability remains outside 01K and deferred according to the live roadmap. No AWS/provider PASS is claimed here. The historical `v1.0.1` release/tag remains immutable and was not modified by LRD-01K.
