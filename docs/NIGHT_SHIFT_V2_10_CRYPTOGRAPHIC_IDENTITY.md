# Night Shift V2-10 — Cryptographic Automation Identity

Status: IMPLEMENTED CANDIDATE  
Recorded: 2026-09-28

## Objective

V2-10 turns the declared builder/reviewer identities introduced by V2-09 into
cryptographically verifiable automation identities.

It does not introduce a second cryptographic implementation. Night Shift reuses the
existing provider-neutral trust fabric:

- `CryptoTrustSetV1`;
- `CryptoTrustKeyV1`;
- `AttestationSigner`;
- `CryptoTrustVerifierV1`;
- Ed25519 through the existing Enterprise contracts.

Private-key material is supplied only at runtime and is never part of repository state,
verification bundles, execution receipts, or serialized evidence.

## Verification identity boundary

A verification bundle that may produce `READY_FOR_HUMAN` or `ELIGIBLE_AUTO`
requires two independently verifiable identities:

1. builder — attestation purpose `PROVENANCE`;
2. reviewer — attestation purpose `SECURITY_REVIEW`.

The signing key ID must equal the corresponding declared identity in the
`VerificationBundle`.

Builder and reviewer keys must be different.

Both signatures bind:

- exact VerificationBundle digest;
- exact quorum digest;
- subject Git SHA;
- TaskCapsule digest;
- role;
- declared identity;
- evidence-valid-until timestamp.

Signature expiry must equal the V2-09 evidence expiry.

## Pinned trust set

Verification requires an externally pinned `CryptoTrustSetV1` digest.

The existing crypto-agility layer fails closed on:

- unknown key;
- revoked key;
- signing with a non-ACTIVE key;
- signature issued outside key lifecycle;
- purpose mismatch;
- public-key mismatch;
- trust-set identity mismatch;
- invalid Ed25519 signature.

A manually constructed key ID or 64-hex digest is not sufficient proof of identity.

## Promotion semantics

Promotion ordering is deliberately fail-closed:

`binding → authority → expiry → quorum PASS → cryptographic verification → promotion`

A candidate that is already BLOCKED does not need cryptographic verification.

Any path that can become `READY_FOR_HUMAN` or `ELIGIBLE_AUTO` requires a valid
cryptographic context and both valid verification signatures.

The cryptographic verification digest is included in the promotion decision evidence
and is transitively bound into the controlled-canary execution receipt.

## Signed execution receipt

The controlled canary signs the final canonical `ExecutionReceipt` only after the
receipt is fully constructed.

The receipt signature binds:

- exact receipt digest;
- complete canonical receipt payload;
- signer identity;
- pinned trust-set identity;
- issue/expiry time;
- nonce.

The signature is immediately reverified under the same pinned trust set before the
canary can return PASS.

Mutation of the receipt after signing therefore invalidates both subject and payload
binding.

## Private key boundary

V2-10 never persists private key material.

The repository stores only code, public trust metadata contracts and tests. The probe
uses ephemeral in-memory Ed25519 keys generated for the synthetic run.

Production key custody, hardware-backed signing, remote KMS/HSM adapters and key
provisioning are separate operational concerns and are not claimed by V2-10.

## Publication boundary

V2-10 does not enable unattended publication.

`night_shift.unattended_promotion_enabled` remains `false`.

Controlled canary publication remains disabled.

## Required adversarial evidence

V2-10 regression coverage includes:

- tampered builder signature;
- builder key / declared identity mismatch;
- reviewer key without SECURITY_REVIEW authority;
- pinned trust-set mismatch;
- expired verification signature;
- passing quorum without cryptographic context;
- private-key material absence from serialized signed evidence;
- valid signed execution receipt;
- tampered execution receipt;
- wrong receipt signer identity.

Planned != Implemented != Validated != Certified.  
Evidence Before Conclusion.


## Validation evidence

Local validation before staging freeze:

- focused V2-10 cryptographic identity / promotion / canary tests: PASS;
- tampered builder signature regression: PASS;
- builder key / declared identity mismatch regression: PASS;
- reviewer purpose mismatch regression: PASS;
- pinned trust-set mismatch regression: PASS;
- expired verification signature regression: PASS;
- missing crypto context for nonblocked promotion: PASS;
- signed-evidence private-key absence check: PASS;
- signed execution receipt verification: PASS;
- tampered execution receipt regression: PASS;
- wrong receipt signer identity regression: PASS;
- full Night Shift test set: PASS across 33 test files;
- Ruff: PASS;
- Mypy Linux target: PASS across 861 source files;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS;
- controlled canary cryptographic integration: PASS.
