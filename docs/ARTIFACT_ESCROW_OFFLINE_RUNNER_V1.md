# LRD-01C — Artifact Escrow & Offline Replay Runner v1

Status: `IMPLEMENTATION CANDIDATE`
Parent program: `continuous LRD-01`
Measured base: `main @ 68eed07c8f6bd70cd805758c88c0ffaf56122d39`
Historical release baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

LRD-01B closes exact identity, preservation-state, semantic-result and immutable replay-capsule
contracts, but it deliberately does not prove that a `PRESERVED` artifact's exact bytes can be
recovered from a replaceable storage backend and re-verified under a least-privilege offline
execution boundary.

An identity-only archive is insufficient for 10+ year replay. A filename, URI, database row or
storage location can continue to exist while the underlying bytes change. Likewise, an archive
can be correctly content-addressed but still be unsafe to restore if extraction permits path
traversal, symlink escape, special members or unbounded expansion.

LRD-01C closes this physical-preservation and bounded offline-verification slice. It does not yet
implement the complete Frozen Path / Current Path semantic execution comparison; that remains
LRD-01D.

## 2. Existing evidence reused

LRD-01C extends existing contracts rather than replacing them:

- `LongRangeReplayManifestV1` remains the immutable logical artifact inventory and preservation
  status authority for LRD execution closure;
- `ContentAddress` remains the existing LUKART content-address contract for canonical structured
  identities;
- `CaseReplayV2` and the Canonical Case Ledger remain authoritative for replay/case-history
  identity; escrow has no CCL write path;
- DR-02 establishes that storage-profile identity is distinct from Product/case identity and
  that alternate storage requires explicit conformance rather than name-based compatibility;
- SSC-02 already proves verifier-first physical source/dependency continuity and supplies the
  fail-closed path/symlink pattern used by LRD-01C;
- the existing Enterprise `ProcessIsolationExecutor` supplies a real child-process lifetime
  boundary, sanitized environment, ephemeral workspace, hard timeout, audit-hook capability
  policy and POSIX resource limits where supported.

The existing isolation layer explicitly does **not** claim a kernel/container sandbox. LRD-01C
preserves that truth boundary: its receipt records `kernel_sandbox=false` and the precise network,
filesystem, process and native-FFI enforcement actually observed.

## 3. Alternatives and decision

### A. Store bytes directly inside `LongRangeReplayManifestV1`

Rejected. It would retroactively widen LRD-01B semantics, couple logical replay identity to one
physical packaging scheme and make historical 01B manifests appear to contain bytes they never
preserved.

### B. Filename/URI based archive index

Rejected. Location and filename are mutable infrastructure metadata, not artifact identity.
Name-based equivalence cannot detect substitution and is not storage-portable.

### C. Backend-neutral raw-byte escrow projection over LRD-01B — selected

The selected design adds a separately versioned physical-preservation projection:

`LRD-01B logical identity -> escrow binding -> exact raw-byte sha256 + size -> replaceable backend`

The binding is content-addressed and includes the exact LRD artifact role/logical identity plus
the raw byte identity. Backend paths are intentionally absent. A backend migration is accepted
only if bytes re-verify to the same exact byte identity.

### D. New container/VM sandbox authority

Rejected for this slice. LRD-01C reuses the tested Enterprise process/capability isolation
boundary and reports its actual strength. Claiming kernel network isolation without separately
implemented host/container controls would violate Evidence Before Conclusion. A stronger future
sandbox may be introduced behind a separately versioned runner profile without changing escrow
identity.

## 4. Contracts

### 4.1 `EscrowBlobIdentityV1`

Schema: `lukart.artifact-blob.v1`

Fields:

- digest algorithm: exactly `sha256` in v1;
- digest: lowercase 64-character raw-byte digest;
- exact byte size.

The identity contains no path, URI, bucket, backend name or filename.

### 4.2 `EscrowArtifactBindingV1`

Schema: `lukart.artifact-escrow-binding.v1`

Binds:

- one fixed `ReplayArtifactRole` from LRD-01B;
- the exact LRD logical `ContentAddress`;
- exact `EscrowBlobIdentityV1`;
- artifact kind `BLOB` or `ZIP`;
- a content-addressed binding identity.

Changing the logical identity, raw bytes, size or kind changes/rejects the binding. The byte
digest is not silently substituted for the higher-level semantic/logical artifact identity;
both are retained because they answer different provenance questions.

### 4.3 `ArtifactEscrowManifestV1`

Schema: `lukart.artifact-escrow-manifest.v1`

The manifest binds one exact `LongRangeReplayManifestV1` and must contain exactly one byte binding
for every LRD artifact whose preservation state is `PRESERVED`, no more and no less.
`REFERENCE_ONLY` and `UNAVAILABLE` artifacts cannot be falsely upgraded by inserting an escrow
binding into this projection. Every role's logical identity must exactly match LRD-01B.

The manifest is immutable/content-addressed verification evidence only. It is not a case-history,
Gold, policy, trust, Product or release authority.

## 5. Filesystem escrow backend

`FileSystemEscrowBackendV1` is the first concrete adapter for the backend-neutral
`ArtifactEscrowBackendV1` protocol.

Storage layout is an implementation detail:

`sha256/<digest-prefix>/<full-digest>`

Properties:

- publication uses create-exclusive semantics; no update/delete/overwrite API exists;
- existing content-addressed paths are accepted only after full byte re-verification;
- every read verifies regular-file type, exact size and SHA-256 before bytes are returned;
- root and path traversal through symlinks fail closed;
- writes use `O_NOFOLLOW` where the host exposes it and are made read-only after publication;
- restore refuses an existing destination instead of overwriting it;
- backend-to-backend migration reads and verifies source bytes, publishes to the target, then
  re-reads the target and requires identical byte identity.

Filesystem immutability is an application contract, not a claim about external administrator or
physical-media controls. External mutation is detected on the next verified read.

## 6. Bounded ZIP restore

ZIP is the only archive kind accepted by the generic LRD-01C archive adapter in v1. Other archive
formats require a separately implemented/versioned adapter.

Before any extraction publication, the complete ZIP central directory is checked for:

- absolute, parent (`..`), empty/dot, backslash or drive-style path escape;
- duplicate canonical member paths;
- Unix symlink members;
- device/special members;
- encrypted members;
- maximum archive bytes;
- maximum member count;
- maximum per-member expanded bytes;
- maximum aggregate expanded bytes;
- maximum compression ratio.

Extraction occurs in a sibling temporary directory with exclusive file creation and symlink
checks. Only a fully successful extraction is renamed into a previously non-existent destination.
A failure removes the temporary directory and never publishes partial output.

The default deterministic bounds are implementation limits, not long-term immutable policy. A
future profile can version them explicitly if LRD operational evidence requires different values.

## 7. Least-privilege offline runner

`OfflineReplayRunnerV1` intentionally exposes one fixed operation: verification of the escrow
material bound to one exact LRD case/manifest. It does not accept an arbitrary caller-supplied
module/function command.

The runner reuses `ProcessIsolationExecutor` with:

- a separate spawned child process;
- hard elapsed-time termination;
- sanitized environment;
- ephemeral temporary workspace;
- read access limited to the LUKART/runtime roots required by the existing executor plus the
  selected escrow root;
- writes limited to the ephemeral workspace;
- network `OFF` under the existing Python runtime guard and socket audit policy;
- process spawning denied;
- native FFI denied;
- POSIX memory/CPU limits when the host supports `resource` controls.

Inside the child, a deliberate network lookup probe must fail with `PermissionError`; otherwise
the run fails. The child re-parses both LRD and escrow manifests, verifies exact case scope and
re-verifies every blob. ZIP bindings also pass bounded archive preflight.

The deterministic receipt records the observed enforcement strings and
`kernel_sandbox=false`. Therefore `network OFF` in LRD-01C means the tested Python
runtime/capability boundary used by LUKART, not a fabricated host firewall or network namespace
claim.

The runner has zero CCL, Product, Gold, policy/trust-promotion or release mutation API. Its
escrow backend exposes no update/delete operation.

## 8. Fail-closed and adversarial acceptance

The focused/adversarial suite must prove at least:

- deterministic raw-byte identity independent from backend location;
- one-byte stored-artifact tampering rejection;
- exact byte-size mismatch rejection;
- exact `PRESERVED` role coverage and logical-identity substitution rejection;
- unknown manifest field and content-address tampering rejection;
- alternate-storage verified restore preserving byte identity;
- restore path traversal rejection;
- restore symlink escape rejection;
- ZIP traversal rejection;
- ZIP symlink rejection;
- compression-ratio and aggregate expansion bomb rejection;
- safe archive extraction with no overwrite/partial publication;
- blob size/member-count bounds;
- exact case-scope/cross-case substitution rejection;
- actual offline child network probe denial;
- tampered escrow rejection inside the child process;
- ZIP bomb preflight inside the child process;
- explicit refusal to promote the receipt to an unimplemented kernel sandbox.

Any repair creates a fresh candidate SHA and invalidates earlier PASS evidence.

## 9. Non-claims

LRD-01C engineering evidence does **not** claim:

- independently evidenced 10+ year external storage durability or media SLA;
- geographic/off-site redundancy unless separately measured;
- WORM hardware/object-lock enforcement;
- kernel/container/VM sandboxing;
- deterministic re-execution of historical external providers/models;
- complete Frozen Path / Current Path semantic comparison;
- independent security, archival or cryptographic certification;
- a new release or change to historical `v1.0.1`.

These boundaries are deliberate. Missing external durability evidence remains UNKNOWN rather than
being inferred from successful repository CI.

## 10. Definition of Done

LRD-01C closes only after one exact implementation SHA proves:

1. strict content-addressed byte/binding/manifest contracts;
2. verified immutable publication and read semantics;
3. alternate-backend identity-preserving restore;
4. bounded archive restore with traversal/symlink/bomb resistance;
5. least-privilege fixed-entrypoint child runner with demonstrated network denial;
6. focused and adversarial tests;
7. Ruff, strict MyPy, full repository regression and security/policy gates;
8. all exact PR-head CI terminal `SUCCESS`;
9. unchanged-head guarded merge;
10. resulting-main post-merge validation terminal `SUCCESS`;
11. immutable v1.0.1 tag/target/release baseline unchanged;
12. canonical closure evidence merged into the GitHub roadmap/plan.

Only then may LRD-01D begin as the next implementation slice.

## 11. Next slice

`LRD-01D — Frozen Path / Current Path / drift evidence` will consume the exact verified bytes from
01C and the identity/assurance semantics from 01B to reconstruct deterministic historical stages,
reuse verified preserved external outputs where appropriate, execute the current supported stack
as a new identity, and separate semantic drift from presentation-only drift.
