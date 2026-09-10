# LRD-01I — Offline Long-Range Survivability Package v1

Status: `IMPLEMENTATION CANDIDATE`
Parent program: `continuous LRD-01`
Depends on: LRD-01B, LRD-01C and SSC-02 engineering closures
Provider boundary: `LOCAL / PROVIDER-NEUTRAL / NO AWS REQUIRED`
Historical release baseline: `v1.0.1` remains outside this stage's authority
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

The long-range controls already preserve complementary parts of the recovery problem:

- LRD-01B binds the complete long-range logical identity and Replay Capsule V1;
- LRD-01C binds every `PRESERVED` LRD role to exact bytes in replaceable escrow and verifies
  those bytes under a bounded offline execution boundary;
- SSC-02 preserves exact Git source, lock/build inputs, physical dependency/build wheels and a
  standard-library verifier sufficient for measured registry-independent rebuild recovery;
- CASE-OPS-03/04 protect private local evidence recovery, but intentionally remain a separate
  private-evidence custody boundary.

These capabilities are individually valuable but they do not provide one provider-neutral
physical package binding the complete LRD replay capsule, all escrowed replay bytes and the exact
SSC-02 reconstruction material. Loss of GitHub/PyPI/current development infrastructure could
therefore leave several separately correct artifacts whose required relationship was not itself
physically packaged and independently verifiable.

LRD-01I closes that composition gap. It does **not** claim bare-metal recovery on arbitrary future
hardware and does not claim that a Python interpreter binary has been physically preserved.

## 2. Selected design

The selected v1 design is one directory-based, content-addressed survivability bundle:

`LRD-01B manifest/capsule + LRD-01C escrow bytes + SSC-02 continuity bundle -> LRD-01I bundle`

The package contains:

- `survivability.json` — exact outer identity, bootstrap contract and exhaustive inventory;
- `identity/long-range-manifest.json` — exact LRD-01B manifest snapshot;
- `identity/replay-capsule.json` — exact Replay Capsule V1 snapshot;
- `identity/artifact-escrow-manifest.json` — exact LRD-01C physical binding snapshot;
- `escrow/sha256/...` — exact bytes for every LRD role declared `PRESERVED`;
- `supply-chain/...` — the complete already-verified SSC-02 continuity bundle;
- `verifier.py` — standalone standard-library outer verifier.

The directory format is chosen instead of inventing a second archive authority. It composes the
existing SSC-02 directory format and LRD-01C content-addressed blob layout, remains easy to copy to
other media/backends, and permits exact inventory verification without extraction risk.

## 3. Construction gate

A bundle may be created only when:

1. the LRD manifest verifies under the production LRD-01B parser;
2. the Replay Capsule embeds exactly that same LRD manifest;
3. **every fixed LRD artifact role is `PRESERVED`** — `REFERENCE_ONLY` or `UNAVAILABLE` fails closed;
4. the Artifact Escrow manifest verifies against that exact LRD manifest;
5. every escrow blob is reread through `FileSystemEscrowBackendV1` and exact SHA-256/size verified;
6. the supplied SSC-02 bundle passes the production SSC-02 verifier;
7. SSC-02 `source_sha` equals the historical LRD `code_commit_sha`;
8. all copied paths are regular non-symlink files within fixed size/file-count bounds;
9. the complete staged bundle passes the standalone outer verifier before atomic publication.

The builder refuses an existing destination and publishes only after complete staging verification.

## 4. Standalone verification boundary

`core.offline_survivability_verifier_v1` intentionally imports only Python standard-library
modules. Its exact source is copied into each package as `verifier.py`.

Given an externally pinned `bundle_digest`, it independently verifies:

- strict outer schema and key set;
- canonical bundle digest;
- exhaustive exact file inventory with SHA-256 and size;
- no symlinks, undeclared files, path traversal or non-canonical paths;
- exact LRD manifest content identity and all-`PRESERVED` fixed role inventory;
- exact Replay Capsule identity and embedded LRD equality;
- exact Artifact Escrow manifest/binding/blob identities and physical blob coverage;
- exact SSC-02 manifest digest, historical source SHA and runtime/platform declarations;
- exact SSC-02 physical inventory bytes.

The expected outer digest must be pinned independently. Rewriting the package plus its internal
manifest cannot satisfy verification against the historical pinned digest.

After outer verification, the preserved `supply-chain/verifier.py` remains available for the deeper
SSC-02 source/wheel/build contract verification and offline reconstruction path.

## 5. Bootstrap contract

The v1 bootstrap contract is fixed:

- network: `DENY`;
- package registry: `NONE`;
- source host/GitHub: `NONE`;
- provider access: `NONE`;
- a compatible Python interpreter is required;
- `physical_interpreter_preserved = false`.

SSC-02 already binds the measured Python implementation/version/cache tag and platform
system/machine. LRD-01I carries that identity into the outer bundle. A future different interpreter
or platform is therefore a new compatibility/migration question, not an implicit v1 PASS.

This is deliberately future-resistant rather than future-predictive. Physical interpreter/runtime
preservation may be added later only through a separately measured/versioned adapter.

## 6. Security / authority boundary

LRD-01I is immutable recovery/verification material only. It adds no:

- Canonical Case Ledger write path;
- Product truth or epistemic promotion authority;
- Gold mutation authority;
- policy/trust-root promotion authority;
- provider credential or AWS authority;
- release/tag authority;
- independent review/certification authority.

Private CASE-OPS evidence capsules are not automatically copied into the public/generic LRD-01I
package. Any future composition with private recovery media requires a separately authorized
privacy/custody design.

## 7. Adversarial acceptance

The stage must fail closed for at least:

- one-byte escrow mutation;
- missing or extra bundle file;
- symlink substitution;
- altered outer manifest even if its internal digest is recalculated when the historical outer
  digest remains pinned;
- replay-capsule/LRD substitution;
- escrow logical-identity or blob substitution;
- any non-`PRESERVED` LRD artifact role;
- SSC-02 source SHA different from the historical LRD code SHA;
- SSC-02 physical inventory mutation;
- unknown outer schema/fields/roles/bootstrap contract;
- unsafe/non-canonical paths;
- unsupported future platform/interpreter claims being promoted implicitly.

Existing LRD-01B/01C, SSC-02, replay, recovery and security/policy suites remain regression
dependencies.

## 8. Explicit non-claims / residual risk

Engineering PASS for LRD-01I does not prove:

- physical preservation of a Python interpreter, OS, firmware or hardware;
- universal future-platform executability;
- external/geographic/independent media durability;
- ransomware-proof storage;
- AWS/provider durability;
- ten-year storage SLA;
- deterministic rerun of historical external providers/models;
- human-independent custody or independent security certification.

The largest remaining execution risk is interpreter/platform obsolescence. LRD-01I makes that risk
explicit and binds the exact measured runtime/platform instead of hiding it. The approved later
cross-environment replay stage can then test migration/compatibility without rewriting this
historical package.

## 9. Definition of Done

LRD-01I may become `CLOSED / ENGINEERING PASS` only after one fresh exact implementation line proves:

1. strict outer bundle/content identity and exhaustive physical inventory;
2. exact LRD-01B manifest/capsule binding;
3. all fixed LRD material physically `PRESERVED` and covered by LRD-01C escrow bytes;
4. exact SSC-02 source/runtime/build material binding to the same historical code SHA;
5. standalone stdlib verification with externally pinned bundle digest;
6. focused/adversarial tests and LRD-01B/01C/SSC-02 regression;
7. Ruff, strict MyPy, full repository and security/policy gates;
8. exact candidate SHA with all required CI terminal `SUCCESS`;
9. unchanged-head/base guarded merge;
10. resulting-main post-merge validation;
11. historical `v1.0.1` tag/target/release unchanged;
12. canonical closure evidence without provider/interpreter/durability overclaim.

## 10. Ordered continuation

After 01I engineering closure, the owner-approved provider-neutral sequence continues with
**crypto migration/renewal**, then **cross-environment replay**, expanded critical-invariant
verification and further provider-neutral durability/recovery. LRD-01H live AWS provider evidence
remains deferred to the March 2027 execution window and no 01I result may be used as an AWS PASS.
