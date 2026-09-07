# Signed Case Exchange v1

Status: XCH-01 implementation contract.

## Purpose

Signed Case Exchange v1 provides a portable, offline-verifiable transport envelope for
an exact `CaseReplayBundleV2`. It does not create another case store, does not import or
merge case history, and does not promote any assertion to epistemic truth.

The Canonical Case Ledger remains the only authoritative writable SSOT for case history.

## Trust boundary

The envelope binds:

- one exact Case Replay v2 bundle and its content address;
- explicit source tenant and source case;
- explicit recipient tenant and recipient case;
- source authorization evidence requiring `case:read`;
- recipient authorization evidence requiring `case:write`;
- the exact exchange request identity in both authorization decisions;
- the existing Enterprise Ed25519 attestation;
- an explicit exchange attestation domain;
- an explicit semantic statement that attestation proves origin/integrity only;
- one content-addressed exchange identity.

`case:write` on the recipient side is authorization evidence for the declared destination.
XCH-01 itself performs no write, restore, merge or import operation.

## Cryptographic design

XCH-01 reuses the existing Enterprise `AttestationSigner` and `AttestationVerifier`
instead of creating a second cryptographic stack.

The signature uses the existing `PROVENANCE` attestation purpose. Domain separation is
made explicit inside the signed payload by:

`lukart.case-exchange.attestation-domain.v1`

The attestation subject is the exact Case Replay bundle digest. The signed payload binds
the request, complete replay bundle snapshot, source authorization and recipient
authorization.

Trusted public keys and revocation state are verifier inputs. Private key material is
never stored in the repository or exchange contract.

## Authorization contract

The source authorization must be an allowed Enterprise authorization decision for:

- the declared source tenant;
- the declared source case;
- `Permission.CASE_READ`;
- the exact exchange request digest.

The recipient authorization must be an allowed Enterprise authorization decision for:

- the declared recipient tenant;
- the declared recipient case;
- `Permission.CASE_WRITE`;
- the exact exchange request digest.

The envelope carries enough authorization-decision and resource metadata to recompute and
verify their content digests offline. Unknown authorization schemas, changed resource
scope, changed request identity or changed permissions fail closed.

This does not imply that source and recipient have a shared epistemic authority. It only
proves that explicit scoped authorization evidence was bound to the signed transport
artifact.

## Offline verification

`verify_signed_case_exchange()` requires only:

- the serialized exchange envelope;
- trusted public keys / revocation state;
- a caller-supplied verification time.

Verification performs, in order:

1. strict exact-key and schema checks;
2. exact exchange-request identity verification;
3. full Case Replay v2 verification and projection rebuild;
4. source case equality with the replay manifest;
5. source authorization identity, decision, permission and scope checks;
6. recipient authorization identity, decision, permission and scope checks;
7. Ed25519 attestation verification for provenance purpose, subject and payload;
8. expiration / revocation / trusted-key checks;
9. exact exchange-envelope content-address verification.

Any failure aborts verification. No partial PASS result exists.

## Epistemic semantics

The canonical semantic marker is:

`origin-integrity-only-not-epistemic-truth`

A valid signature proves cryptographic origin/integrity relative to a trusted key and the
bound payload. It does not prove that evidence is factually correct, does not resolve
contradictions and does not convert claims into FACT.

Case Replay v2 continues to rebuild the exact Epistemic v2 and Evidence Trust Graph
projections contained in the exchanged case history.

## Non-authority guarantees

`core.case_exchange_v1` contains no:

- `CanonicalCaseLedger` writer;
- `append_event` path;
- SQLite persistence;
- restore operation;
- merge/import authority.

Receiving an exchange envelope therefore cannot silently alter canonical history.
A future import/acceptance stage must be separately specified, authorized, migration-aware
and validated.

## Failure model

The contract fails closed for, among other conditions:

- unknown top-level fields or schemas;
- malformed content addresses;
- source case not matching the replay bundle;
- replay tampering;
- stale or rebound request identity;
- source/recipient permission mismatch;
- tenant or case substitution;
- authorization decision/resource digest mismatch;
- untrusted or revoked signing key;
- wrong attestation purpose, subject or payload;
- expired or not-yet-valid attestation;
- changed attestation domain or epistemic semantics;
- exchange content-address mismatch.

## Determinism and identity

The request, both authorization records and final exchange envelope are content-addressed.

For identical replay bytes, request, authorization evidence, signing key, issue/expiry
times and nonce, Ed25519 produces the same signature and therefore the same exchange
identity. Any recipient, request, replay or authorization change produces a distinct
identity.

## Scope of XCH-01

XCH-01 establishes signed portable exchange and offline verification only.

It deliberately does not implement:

- automatic case import;
- cross-case epistemic trust promotion;
- automatic conflict resolution;
- key-discovery PKI;
- long-term timestamp authority;
- cryptographic algorithm migration beyond the existing versioned Enterprise contract.

Those require separate evidence, design and approval.
