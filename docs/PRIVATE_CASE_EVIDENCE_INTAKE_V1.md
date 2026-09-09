# Private Case Evidence Intake v1

Status: CASE-OPS-01 engineering contract.

## Decision

Real case evidence is a private/local input and MUST NOT be written to the public repository,
public CI artifacts, workflow logs, fixtures, or telemetry. Public GitHub contains only code,
schemas, policy, documentation, and synthetic test data.

The Canonical Case Ledger (CCL) remains the only writable source of truth for case history.
The private evidence store is not a second ledger. It stores immutable encrypted evidence bytes
and digest-bound provenance objects. A CCL event may reference only the exact `evidence_id`,
`manifest_digest`, `receipt_digest`, and opaque `case_scope_digest` returned by the store.

## Identity and crypto contract

Evidence identity is `sha256:<hex>` over plaintext bytes. Filename, filesystem location,
encryption nonce, key rotation, and ciphertext are not evidence identity. The envelope is
versioned and uses AES-256-GCM from `cryptography`, a fresh 96-bit nonce, explicit key id/version,
and authenticated additional data binding schema, opaque case scope, evidence identity, size,
and key identity. Ciphertext/envelope identity is independent from plaintext evidence identity.

Keys and credentials MUST come from a runtime key provider. Production/private keys MUST NOT be
hard-coded, committed, logged, or exposed to GitHub Actions. Unknown key, wrong key, invalid
scope, unsupported schema/algorithm, tampering, missing provenance, or authorization failure is a
fail-closed error.

## Storage and privacy boundary

Object paths are derived from cryptographic digests, never source filenames. Persisted manifest,
receipt, and source-index objects contain opaque digests instead of raw source references. New
operational ingestion MUST NOT create plaintext `original/`, `extracted/`, or `markdown/`
evidence artifacts. Extracted text is a DERIVED encrypted evidence object.

The existing local case directory may contain case metadata required by the private product
runtime, but evidence byte objects and their immutable provenance are held under the encrypted
private-evidence boundary. Logging must not emit evidence content, raw source references,
filenames, names, national identifiers, or key material.

## Import semantics

- Same plaintext bytes always produce the same evidence identity.
- Re-import of the same logical source and same bytes is idempotent.
- Same logical source with different bytes is a mutation conflict and fails closed; the caller
  must provide a new source identity or explicitly model a new evidence event in CCL.
- Renaming a file does not alter evidence identity.
- PRIMARY, SECONDARY, and DERIVED evidence kinds are explicit manifest fields.
- Receipt and manifest objects are canonical JSON and digest-bound.
- Source indexes are integrity-checked lookup aids and are not case-history authority.

## Authorization

Read and write are case-scoped and deny by default through the existing enterprise
`AuthorizationContext`. Private evidence construction requires `evidence:read` in the exact case
scope. Import additionally requires `evidence:write`. Cross-tenant and cross-case access is
rejected.

## Offline verification, backup, and restore

Verification authenticates and decrypts the exact envelope, then recomputes plaintext SHA-256 and
size before accepting the bytes. It requires no provider, model, agent, network, or cloud storage.
Backup copies ciphertext and provenance only; restore rejects symlinks and requires the same
scope/authorization/key contract before plaintext can be verified.

## Adversarial requirements

Synthetic tests cover round-trip identity, duplicate idempotence, mutation conflict, rename
stability, nonce/ciphertext separation, missing write permission, cross-case scope, wrong key,
ciphertext tamper, manifest/receipt tamper, truncation, source/root symlink escape, sensitive
source-reference non-persistence, CCL reference minimization, and alternate-root backup/restore.

GitHub Actions remains synthetic-only. No workflow requires or may receive a private evidence
store credential, private case path, or real case artifact.

## Authorized non-cloud continuation

`CASE-OPS-02 — Local Evidence Derivation & Replay Binding v1` is the approved additive
continuation under the active `continuous LRD-01` program. It MUST reuse this encrypted evidence
boundary, MUST NOT introduce cloud/provider storage or a second case-history authority, and MUST
represent external-tool OCR as environment-bound unless stronger exact replay evidence exists.
Architecture contract: `docs/LOCAL_EVIDENCE_DERIVATION_V1.md`.
