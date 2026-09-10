# CASE-OPS-07 — Environment-Bound OCR Replay Verification v1

Status: `CASE-OPS-07 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-06 — Private Local End-to-End Pilot Evidence`
Deployment boundary: `PRIVATE LOCAL / NON-CLOUD`

## Problem

CASE-OPS-02 correctly classifies local Tesseract OCR as `ENVIRONMENT_BOUND`. Its immutable
derivation receipt binds the exact source evidence, transform/config identities, exact derived
evidence and an opaque identity of the resolved Tesseract executable plus version-command output.
CASE-OPS-06 proves that a verified private projection can traverse CCL, Product Runtime and Case
Replay. The remaining measured gap is narrower: there is no machine-verifiable operation that
re-executes one recorded `ENVIRONMENT_BOUND` OCR derivation and proves whether the currently
observed output is exactly the recorded output.

This stage does not create a new OCR engine and does not claim environment-independent
determinism.

## Alternatives considered

1. No change — rejected because an operator cannot turn the recorded OCR provenance edge into an
   observed replay proof.
2. Promote Tesseract OCR to `DETERMINISTIC` or `IDENTICAL` when bytes happen to match — rejected as
   false assurance because linked libraries, language data and host state are not fully frozen.
3. Introduce cloud OCR or provider escrow — rejected because no provider deployment is authorized
   and it does not solve the local replay semantics problem.
4. Freeze a complete VM/container/model/language-data capsule now — stronger isolation, but larger
   migration, supply-chain and long-term maintenance surface than the demonstrated gap.
5. Reuse CASE-OPS-02 identities and perform fail-closed observed replay — selected as the smallest
   justified solution.

## Contract

The verifier accepts only an existing, fully verified CASE-OPS-02 derivation receipt whose:

- replay class is exactly `ENVIRONMENT_BOUND`;
- transform id is exactly `lukart.tesseract-ocr-pol-eng-psm6`;
- transform version is exactly `1`;
- canonical config digest matches `language=pol+eng`, `psm=6`, `transport=stdin`;
- source is verified image evidence in the same private case scope;
- recorded tool-identity digest is a valid content identifier.

Before OCR execution, the verifier resolves the current local Tesseract executable and recomputes
the existing CASE-OPS-02 tool identity. A mismatch with the recorded digest is
`environment drift` and fails closed without accepting a replay result.

The exact decrypted source bytes are then supplied through the existing stdin transport. The tool
identity returned by the execution path is checked again to detect a tool change across the
execution boundary. The normalized observed UTF-8 output must be byte-identical to the already
verified encrypted DERIVED evidence. Any mismatch fails closed.

A successful result emits a content-addressed digest-only proof containing only case-scope,
derivation, source/output, transform/config and tool identity digests plus status `MATCH`. It does
not contain OCR text, source names, local paths, key material or credentials. The proof is
verification evidence, not case-history authority; CCL remains the sole authoritative writable
SSOT.

## Replay semantics

A CASE-OPS-07 PASS means:

> under the currently observed CASE-OPS-02 tool identity and fixed OCR profile, re-execution over
> the exact source bytes produced the exact recorded derived bytes.

It MUST NOT be interpreted as proof that all material environment dependencies were identical or
that future re-execution is guaranteed. The replay class remains `ENVIRONMENT_BOUND` even after a
matching replay.

## Bounds and fail-closed behavior

- source replay ceiling: 64 MiB;
- observed OCR output ceiling: 16 MiB;
- existing Tesseract execution timeout remains authoritative;
- missing Tesseract, invalid/unknown receipt identity, unsupported replay class/transform/version/
  config, non-image source, source/output budget overflow, tool drift, tool change during execution,
  source tampering or output mismatch all fail closed;
- proof output is immutable, mode `0600`, and must remain outside the public repository;
- no CCL write path is introduced.

## Privacy and validation boundary

GitHub Actions uses synthetic evidence and a synthetic Tesseract executable/subprocess only. Real
case bytes, private keys, OCR text and local proof files are never public-CI inputs or artifacts.
The operator CLI requires an explicit private-local-case declaration and read-only evidence
authorization.

Focused/adversarial validation must prove exact replay match without replay-class promotion,
pre-execution executable drift rejection, same-tool output mismatch rejection, unsupported config
and deterministic-derivation rejection, source/output budgets, immutable digest-only proof output
and refusal to write proof evidence into the public repository. CASE-OPS-02 derivation and case
ingestion tests remain regression dependencies.

Full repository regression, lint/type checks, security/policy gates, exact-SHA CI, guarded merge
and post-merge validation remain mandatory before engineering closure.

## Residual risk / next improvement

The largest deliberate residual is unchanged from the underlying `ENVIRONMENT_BOUND` model: the
recorded tool identity does not freeze every linked library, locale, Tesseract traineddata file or
host execution dependency. CASE-OPS-07 contains this risk by proving observed equality and by
refusing to promote the replay class. If measured operational evidence later shows that restoring
the same executable is insufficient, a separately versioned migration may add a complete runtime
fingerprint or frozen offline execution capsule. Such a migration must not rewrite historical
CASE-OPS-02 evidence identities.

This contract is an engineering control only. It does not claim a real private-case replay drill,
independent review, external certification, cloud durability or security certification.
