# CASE-OPS-03 — Offline Local Recovery Capsule & Key Recovery v1

Status: `CASE-OPS-03 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-02 — Local Evidence Derivation & Replay Binding v1`
Deployment boundary: `LOCAL / NON-CLOUD`

## Problem

CASE-OPS-01/02 protect private evidence bytes, provenance, derivations and runtime projection, but the existing `backup_to()` operation copies ciphertext/provenance only. Decryption keys remain external runtime dependencies. Loss of the workstation or key file can therefore leave a byte-complete encrypted backup that is permanently unreadable. The legacy backup also has no authenticated snapshot proving exact physical completeness of all encrypted evidence/provenance files.

The required improvement is disaster recovery for the private evidence boundary without moving real case data to cloud storage, persisting plaintext evidence, weakening CCL authority or introducing a second case-history backup format.

## Evidence and alternatives

Existing controls already provide AES-256-GCM evidence encryption, immutable/content-addressed manifests and receipts, additive key rotation, CASE-OPS-02 derivation receipts, offline verification, tenant/case authorization and local path isolation.

Material alternatives:

1. **No change.** Rejected: loss of the only external key file remains catastrophic even when ciphertext backup survives.
2. **Duplicate raw key files with the backup.** Rejected: raw key custody is weak, rotation produces multiple required keys, and ciphertext plus raw key in one uncontrolled copy collapses the encryption boundary.
3. **OS-bound keystore/DPAPI as the recovery authority.** Rejected as the v1 portability baseline: it binds disaster recovery to a specific platform/user/profile and can prevent recovery on a replacement machine. A later adapter may use OS/HSM protection as an additional layer.
4. **Passphrase-wrapped multi-key recovery keyset + authenticated physical snapshot.** Selected as the smallest provider-neutral non-cloud design that closes both key-loss and silent-incomplete-backup gaps.

## Trust and authority boundary

The Canonical Case Ledger remains the sole authoritative writable SSOT for case history. CASE-OPS-03 does **not** back up, rewrite, merge or restore CCL history. Existing DR-01 remains the case-history recovery path.

A recovery capsule is immutable recovery evidence for the private encrypted evidence store only. It contains:

- `capsule.json` — versioned capsule metadata;
- `snapshot.json` — canonical ordered inventory of every encrypted evidence/provenance file with exact relative path, size and physical SHA-256 digest;
- `key-envelope.json` — passphrase-authenticated wrapped keyset;
- `evidence/` — exact ciphertext/provenance tree.

No plaintext evidence, raw source path, raw source name, raw key file or recovery passphrase is persisted by the capsule implementation.

## Snapshot and completeness contract

The v1 snapshot accepts only the existing digest-sharded private-store categories:

- `objects`;
- `manifests`;
- `receipts`;
- `source-index`;
- `derivations`.

Symlinks, non-regular files, unknown categories, malformed digest paths, unexpected/extra files and hard budget overflow fail closed. The verifier requires an exact physical inventory match: missing, added or modified encrypted/provenance bytes are not tolerated.

Before capsule creation, every manifest/receipt/envelope relation is verified through the existing `PrivateEvidenceStore`, source indexes must resolve to their exact source identity, all CASE-OPS-02 derivation receipts are loaded through the canonical derivation verifier, and orphan encrypted objects or unbound receipts fail closed.

This strictness deliberately treats leftover/unbound immutable objects as recovery-unsafe rather than silently deciding which bytes should survive a disaster.

## Key recovery contract

Every distinct `(key_id, key_version)` referenced by an accepted manifest is required at capsule creation. This includes historical keys needed to read evidence that predates key rotation. Missing historical key material fails capsule creation.

The sorted exact keyset is encrypted using:

- KDF: `SCRYPT`;
- `N = 32768`, `r = 8`, `p = 1`;
- 16-byte random salt;
- 32-byte derived wrapping key;
- cipher: AES-256-GCM;
- 12-byte random nonce.

The key-envelope AAD binds the exact case-scope digest, recovery schema/profile, exact snapshot digest and exact key count. Consequently, an attacker without the recovery passphrase cannot remove a complete encrypted document/provenance group, recompute an unkeyed snapshot and still authenticate the original key envelope.

Recovery passphrases are obtained interactively by the operator CLI and are never command-line arguments, repository values, CI secrets or log output. The v1 minimum is 12 UTF-8 bytes; operational policy should use a high-entropy memorized/passphrase-manager value.

## Create / verify / restore semantics

`create` requires exact case-scoped `evidence:read` and `evidence:write`, resolves every historical/active key, verifies the complete source store, copies to a staging directory, recomputes the snapshot after copy, verifies the finished capsule and only then atomically publishes the capsule directory.

`verify` requires exact case-scoped `evidence:read`. It verifies capsule schema, case scope, exact snapshot identity, exact physical inventory, key-envelope digest/AAD, passphrase authentication, exact key identities and the complete restored private evidence/provenance graph.

`restore` additionally requires exact case-scoped `evidence:write`, refuses an existing destination, copies only verified encrypted evidence/provenance to staging, re-verifies before atomic publication and re-verifies the final store. Recovered raw AES keys remain only in an in-memory `EvidenceKeyProvider`; the restore operation does not emit raw key files.

Capsule and restore destinations supplied through the operator CLI must be outside the public repository tree. Git ignore rules also exclude `*.mvros-recovery/` as defence in depth.

## Failure and adversarial requirements

Synthetic tests must cover at least:

- multi-key key-rotation recovery, including both historical and active envelopes;
- stable snapshot identity across capsules while salt/nonce produce distinct wrapped-key envelopes;
- no persisted plaintext evidence, raw AES key bytes or passphrase;
- wrong passphrase/authentication rejection;
- missing, additional or modified encrypted/provenance file rejection;
- cross-tenant and cross-case rejection;
- missing historical rotation key rejection;
- CASE-OPS-02 derivation tamper rejection;
- symlink rejection;
- existing restore-target refusal;
- repository-tree capsule refusal;
- deny-by-default recovery export without `evidence:write`.

Public GitHub Actions uses synthetic values only and must never receive a real recovery capsule, real case bytes, private evidence keys or a real recovery passphrase.

## Migration and long-horizon contract

CASE-OPS-03 is additive. Existing CASE-OPS-01/02 evidence identities, ciphertext, derivation identities and CCL history remain immutable. Historical plain directory backups are not retroactively labelled CASE-OPS-03-compliant; they lack the authenticated snapshot/key-envelope contract.

All capsule, snapshot, keyset, KDF and cipher identities are explicit/versioned. Unknown fields, unknown schema/profile, changed KDF parameters or unsupported algorithm fail closed. A future KDF/cipher/key-custody migration requires a separately versioned deterministic migration path and must never rewrite historical evidence identity.

## Non-claims and residual risk

CASE-OPS-03 is an engineering recovery control, not HSM, TPM, DPAPI, independent escrow, geographic durability, ransomware-proof media, external security certification or human-independent custody.

The largest residual risk is now **recovery-passphrase loss or compromise**. Losing both live key files and the recovery passphrase still makes encrypted evidence unrecoverable; compromise of the capsule plus passphrase exposes the wrapped evidence keys. A later stage may add optional split custody / OS-HSM-backed wrapping / offline multi-copy drills if measured operational need justifies it.

A second residual risk is physical co-location: CASE-OPS-03 proves the capsule's completeness and recoverability, not that the capsule exists on a separately durable device/site. Provider/cloud durability remains outside this non-cloud stage and is not implied by engineering PASS.
