# CASE-OPS-02 — Local Evidence Derivation & Replay Binding v1

Status: `CASE-OPS-02 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-01 — Private Case Evidence Intake v1`
Deployment boundary: `LOCAL / NON-CLOUD`

## Problem

CASE-OPS-01 encrypts PRIMARY and DERIVED evidence and protects exact evidence identity, but the
legacy ingestion inventory records only a human-readable extraction method. That is insufficient
to prove which exact source evidence, transform configuration and execution environment produced
a derived text view. Treating all OCR output as deterministically replayable would therefore be
an epistemic and provenance error.

## Evidence and alternatives

Existing capabilities already provide AES-256-GCM private storage, plaintext evidence identity,
case-scoped authorization, encrypted DERIVED objects, offline verification, backup/restore and
CCL-safe digest references. The missing capability is the immutable derivation edge.

Material alternatives considered:

1. No change — smallest code change, but derived output remains under-bound for replay.
2. Parallel derived-data database — rejected because it creates another persistence/authority
   surface and conflicts with the CCL/private-store boundaries.
3. Broad OCR/parser platform — rejected for this stage because parser dependency, sandbox,
   nondeterminism and migration surface would be larger than the demonstrated gap.
4. Reuse the existing private evidence store and add a content-addressed derivation receipt —
   selected as the smallest justified design.

## Contract

A CASE-OPS-02 derivation binds:

- exact source `evidence_id`, manifest digest and import receipt digest;
- opaque case-scope digest;
- transform id and version;
- canonical transform-config digest;
- replay class;
- opaque tool-identity digest when an external local tool participates;
- exact derived `evidence_id`, manifest digest and import receipt digest;
- a semantic derivation identity independent from encryption nonce and filesystem location.

The receipt is canonical JSON, immutable and content-addressed. Its digest is sufficient to
rehydrate the exact source/derived identities from an encrypted backup/restore and then run full
offline verification. It contains no evidence bytes, source filename, case name, person name,
national identifier, filesystem path, key bytes or cloud credential. CCL remains the only
writable case-history SSOT; the derivation receipt is immutable provenance evidence only.

## Replay classes

### `DETERMINISTIC`

The v1 deterministic transform accepts only `text/plain` or `text/markdown`, strict UTF-8,
rejects BOM and NUL, normalizes CRLF/CR to LF and enforces a 16 MiB hard input ceiling. Its
semantic derivation identity binds exact source plaintext identity, transform version and config.
The output is persisted only as encrypted DERIVED evidence.

### `ENVIRONMENT_BOUND`

External local tools do not inherit a deterministic claim. The ingestion adapter classifies
Tesseract OCR as `ENVIRONMENT_BOUND` and binds an opaque digest of the exact resolved executable
bytes plus version-command output, together with fixed OCR configuration. A different tool
identity creates a different semantic derivation identity. Same semantic identity producing
different bytes is a mutation conflict and fails closed.

`ENVIRONMENT_BOUND` MUST NOT be promoted to `IDENTICAL` replay merely because output bytes happen
to match. A future stronger OCR replay class requires separately versioned evidence for all
material runtime/model/language-data dependencies.

## Privacy and execution boundary

- no cloud/provider API is introduced or authorized;
- GitHub Actions uses synthetic bytes only;
- private source bytes are read from the existing encrypted evidence object after import;
- Tesseract receives exact source bytes through stdin, not a source filesystem path;
- stdout-derived text is immediately imported as encrypted DERIVED evidence;
- no plaintext original/extracted/markdown artifact is persisted by operational ingestion;
- logs/errors must not expose source names, evidence content, local paths or key material.

## Fail-closed semantics

Reject unsupported source media, invalid UTF-8, BOM/NUL, size-budget overflow, unknown receipt
fields/schema/replay class, missing or invalid digest identities, source/derived tampering,
cross-case substitution, missing external-tool identity, immutable receipt divergence and same
logical derivation producing different output.

## Migration and compatibility

CASE-OPS-01 manifests/envelopes/receipts remain valid and immutable. CASE-OPS-02 is additive: it
creates new derivation receipts only for derivations executed under this contract. Historical
legacy derived objects are not retroactively labelled CASE-OPS-02-compliant. No migration rewrites
old evidence identity, ciphertext or CCL history.

## Validation

Focused/adversarial tests must prove deterministic text normalization, idempotent replay,
encrypted-at-rest derived bytes, stable semantic identity across equivalent source encryption
manifests, digest-only derivation reload after encrypted backup/restore, tool-identity separation
for environment-bound OCR, exact-byte stdin transport without source-path exposure,
output-divergence rejection, UTF-8/media/budget rejection, receipt tamper/unknown-field rejection
and cross-case denial.

Full repository regression, lint/type checks, security/policy gates and exact-SHA CI remain
mandatory before guarded merge. Real case bytes, private keys and provider credentials are never
CI inputs.

## Residual risk / next improvement

The largest deliberate residual limitation is OCR reproducibility: Tesseract language data,
linked libraries and host execution environment are not yet fully frozen into an offline replay
capsule. The v1 contract contains that risk by reporting `ENVIRONMENT_BOUND` instead of false
`DETERMINISTIC/IDENTICAL`. A later stage may strengthen local OCR sandboxing and complete runtime
fingerprinting if measured product need justifies the additional complexity.
