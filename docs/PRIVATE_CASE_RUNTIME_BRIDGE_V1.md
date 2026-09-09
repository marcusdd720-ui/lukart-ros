# CASE-OPS-02 Repair — Verified Local Evidence Runtime Bridge v1

Status: repair candidate against merged CASE-OPS-02.

## Problem

Merged CASE-OPS-02 establishes provenance-bound local evidence derivation and replay classification. A later audit found two independent operational/trust gaps:

1. `knowledge.models.local_case_runtime` still treated plaintext `document_inventory.json` as the source of evidence references without verifying the encrypted evidence and derivation receipts first.
2. `scripts/ingest_case_documents.py` still called the hardened private ingestion API without the required authorization and key-provider inputs.

These are repair findings. They do not redefine the already merged CASE-OPS-02 derivation contract.

## Decision

Use the existing CASE-OPS-02 derivation receipts as the only runtime locator/provenance input. Do not introduce a second canonical inventory.

`encrypted PRIMARY evidence -> verified derivation receipt -> encrypted DERIVED evidence -> verified runtime projection`

The plaintext compatibility inventory remains local and non-authoritative. Mutation or deletion of that file cannot alter a verified runtime projection. If derivation receipts are missing, tampered, ambiguous, non-contiguous or structurally invalid, runtime construction fails closed and MUST NOT fall back to the compatibility inventory.

## Projection rules

The bridge:

- enumerates the bounded content-addressed derivation receipt set under the private store;
- rejects symlinked, malformed or non-canonical receipt layout;
- calls the canonical CASE-OPS-02 `load_derivation()` verifier for each receipt;
- verifies exact source manifest identity and case scope through existing private-evidence/derivation checks;
- maps source evidence to `DOC-NNN` only through the digest of the canonical `document-slot:N` source identity;
- requires exactly one derivation per contiguous document slot in runtime projection v1;
- rejects duplicate/ambiguous derivations rather than choosing implicitly;
- produces a content-addressed `VerifiedLocalEvidenceProjectionV1` containing evidence/provenance identities only.

This v1 intentionally fails if a future case has multiple derivations for the same source slot. A future policy must explicitly define selection/version semantics before ambiguity is accepted.

## CCL registration

Optional registration uses the existing `CanonicalCaseLedger`; no new writable authority is introduced. Registration requires:

- exact case-scoped `case:write` permission;
- projection case-scope digest equal to the digest of the authorized tenant/case pair;
- every projected document bound to that same scope;
- RuntimeIdentity with declared evidence inventory containing the projection digest;
- exact expected CCL head.

The event is provenance-only. It does not promote derived text to FACT/TRUSTED or authorize reasoning conclusions.

## Local operator key boundary

`LocalFileEvidenceKeyProvider` restores an executable non-cloud CLI path. It accepts one exact key id/version and one non-symlink local file containing exactly 32 raw AES-256 key bytes. On POSIX, group/world-readable key files fail closed. The CLI rejects key files inside the public repository tree and binds authorization to the case manifest's actual `case_id`, not merely its filesystem key.

This is not an HSM/OS-keystore claim. Key escrow, recovery and hardware-backed protection remain separate concerns.

## Non-goals

This repair does not:

- change CASE-OPS-02 derivation identity/replay semantics;
- upload any case data to AWS/cloud/provider storage;
- place real case data or keys into public CI;
- make compatibility inventory authoritative;
- create a second case ledger;
- claim independent/security/external certification;
- retroactively certify pre-CASE-OPS-02 evidence that lacks derivation receipts.

## Adversarial acceptance

Synthetic validation covers compatibility-inventory mutation, derivation tamper/deletion/layout substitution, no plaintext fallback, runtime projection binding, case/tenant authorization, RuntimeIdentity binding, digest-only CCL payload, key identity/length/permissions and the complete existing CASE-OPS-01/02 derivation regression.
