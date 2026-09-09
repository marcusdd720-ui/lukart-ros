# CASE-OPS-02 — Verified Local Evidence Runtime Bridge v1

Status: implementation candidate under owner-approved non-cloud CASE-OPS continuation.

## Problem

CASE-OPS-01 encrypted primary/derived evidence and provenance, but two operational gaps remained:

1. `knowledge.models.local_case_runtime` consumed `document_inventory.json` as ordinary local metadata without cryptographically verifying that its evidence references still matched the encrypted private evidence store.
2. `scripts/ingest_case_documents.py` still called the hardened ingestion API without the now-required authorization and key-provider inputs, so the operator path was not executable after CASE-OPS-01.

A plaintext compatibility inventory MUST NOT become a parallel truth source. The Canonical Case Ledger (CCL) remains the only writable authority for case history.

## Decision

CASE-OPS-02 introduces one fail-closed non-cloud bridge:

`source bytes -> CASE-OPS-01 encrypted evidence -> encrypted canonical runtime inventory -> verified runtime projection -> optional digest-only CCL registration`

The runtime inventory itself is a DERIVED encrypted evidence object with fixed logical source identity `case-ops-runtime-inventory:v1`. Its source index, receipt, manifest, envelope, case scope and plaintext content digest are verified before any document is projected into the local runtime.

The old `document_inventory.json` remains only a compatibility/debug view. Runtime code MUST NOT fall back to it when the encrypted runtime inventory is missing, damaged or unverifiable.

## Verified projection contract

Every runtime document requires all of the following:

- contiguous canonical slot `DOC-NNN`;
- PRIMARY evidence identity, manifest digest and receipt digest;
- PRIMARY manifest bound to exact `document-slot:N` opaque source identity;
- exact plaintext SHA-256 consistency;
- DERIVED text identity and receipt;
- DERIVED manifest bound to exact `derived-text:<primary evidence id>` opaque source identity;
- `text/plain` derived media type;
- exact case-scope digest;
- successful authenticated decryption and content-identity recomputation for all referenced objects.

Unknown fields, schemas, kinds, wrong case scope, missing objects, receipt/manifest/envelope substitution, slot substitution, duplicate primary evidence, non-contiguous slots and plaintext fallback all fail closed.

The resulting `VerifiedLocalEvidenceProjectionV1` is content-addressed. Runtime `EvidenceItem` and graph metadata use only verified identities from that projection; unbound source filename and extraction metadata are not promoted into trusted runtime evidence metadata.

## CCL registration

`register_projection_in_ccl()` is an explicit optional write through the existing `CanonicalCaseLedger`; it does not create another persistence authority.

Registration requires:

- exact case-scoped `case:write` authorization;
- runtime identity with declared evidence inventory;
- runtime identity explicitly containing the projection digest;
- exact expected CCL head;
- digest-only event payload with no evidence plaintext or raw source filename.

The event type is `private.evidence.projection.registered.v1`. Registration records provenance only; it does not promote extracted content to FACT, alter epistemic status, or authorize reasoning conclusions.

## CASE-OPS-01 migration

`migrate_legacy_inventory()` is the only supported v1 migration for pre-CASE-OPS-02 local cases that already contain encrypted CASE-OPS-01 objects but lack the encrypted runtime inventory.

Migration:

1. reads the local compatibility inventory only as untrusted migration input;
2. verifies every referenced encrypted object and slot binding;
3. canonicalizes the exact inventory bytes;
4. imports them as the fixed DERIVED runtime-inventory object;
5. reloads and compares the resulting verified projection.

Identical reruns are idempotent. Divergent content under the same fixed runtime-inventory source identity fails closed rather than silently rewriting history.

## Local key boundary

`LocalFileEvidenceKeyProvider` is a replaceable non-cloud key-provider implementation for operator workflows. It accepts one exact key id/version and one local non-symlink file containing exactly 32 raw AES key bytes. On POSIX, group/world-readable key files are rejected. Key bytes are never placed in repository metadata or logs.

`.mvros-keys/` and `*.mvros-key` are ignored by Git. This provider is an operational local adapter, not a new key authority and not a claim of HSM/OS-keystore equivalence.

## Explicit non-goals

CASE-OPS-02 does not:

- upload case data to AWS or any cloud/provider;
- store plaintext evidence in GitHub, CI, fixtures, telemetry or CCL;
- make the private evidence store a second case-history ledger;
- auto-promote evidence to FACT;
- replace CCL exact-head semantics;
- claim independent security review or external certification;
- claim key escrow/recovery or hardware-backed key protection.

## Adversarial acceptance

Synthetic-only validation must cover at least:

- encrypted runtime inventory round-trip and deterministic projection identity;
- mutation of plaintext compatibility inventory has no runtime effect;
- source-index tamper and deletion fail closed;
- no fallback to plaintext inventory;
- legacy migration idempotence;
- slot/evidence substitution rejection;
- wrong/missing authorization;
- missing runtime-evidence binding for CCL registration;
- no plaintext/source filename in CCL registration event;
- key-file identity, length, symlink/path and POSIX permission controls;
- full CASE-OPS-01 security regression.

No real case artifact or secret is permitted in public CI.
