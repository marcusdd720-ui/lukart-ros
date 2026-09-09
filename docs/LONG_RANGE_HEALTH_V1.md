# LRD-01E — Crypto Renewal / Operational Health v1

Status: `IMPLEMENTATION CANDIDATE`
Parent program: `continuous LRD-01`
Depends on: `LRD-01D CLOSED / ENGINEERING PASS`
Measured base: `main @ a5686e36a6f198fb003125f35efb9ed508099177`
Historical release baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

LRD-01D proves Frozen/Current reconstruction and drift evidence, but a historical PASS is not
current operational health. Long-lived evidence also needs additive cryptographic renewal and a
measured proof that preserved bytes can still move to another storage profile without changing
identity.

LRD-01E closes those gaps without creating a second trust registry, backup format, storage layer,
health SSOT or Product authority.

## 2. Existing authority reused

- CRY-01 (`core.crypto_agility_v1`) remains the only crypto-agility/trust-set/key-lifecycle
  contract. LRD-01E uses its pinned trust-set verification and ACTIVE-only signing.
- DR-02 (`core.enterprise.recovery_continuity_v1`) remains the recovery/storage-conformance
  contract. LRD-01E consumes its manifest/report evidence and PASS/FAIL state.
- LRD-01C (`core.artifact_escrow_v1`) remains physical-byte authority. Portability uses its
  verified read -> content-addressed publish -> identity equality -> verified reread migration.
- LRD-01D remains historical replay/drift evidence. Its PASS never becomes a freshness signal.

All 01E artifacts are immutable, deterministic, content-addressed derived evidence.

## 3. Crypto renewal attestation

Schema: `lukart.lrd-crypto-renewal.v1`.

Renewal is additive. It first verifies the historical attestation under its pinned historical
trust set at the renewal time. The current trust set must explicitly chain to that historical
trust-set digest. A current ACTIVE signer then signs a renewal payload bound to the exact case,
historical attestation digest and historical trust-set digest while preserving the exact subject
and purpose. The new proof is verified immediately under the pinned current trust set.

Renewal does not mutate old bytes/signatures, does not revive revoked evidence, does not allow a
retired key to issue a new proof, does not persist private material and does not promote trust.

## 4. Storage portability drill

Schema: `lukart.lrd-storage-portability-drill.v1`.

The drill requires distinct content-addressed `StorageProfileV1` identities. For every PRESERVED
LRD artifact bound by the exact escrow manifest, it calls the existing `migrate_verified_blob()`.
Success therefore requires verified source read, target publication, unchanged SHA-256/size and
verified target reread. The drill binds case, escrow manifest, source/target profile identities,
artifact count, total bytes, migrated blob-set digest and observation time.

No backend overwrite/update/delete API is introduced.

## 5. Freshness-aware health

Schemas:

- `lukart.lrd-freshness-policy.v1`
- `lukart.lrd-health-report.v1`

Time is an explicit nonnegative epoch-second input. Core logic never calls the wall clock. The
versioned freshness policy separately bounds crypto-renewal, portability and recovery evidence
age. Future-dated evidence fails closed.

Dimension states:

- `FRESH`
- `STALE`
- `MISSING`
- `FAIL`

Aggregate states:

- `HEALTHY` — all required evidence is present, PASS where applicable, and fresh;
- `STALE` — evidence is complete but at least one dimension exceeds its freshness budget;
- `UNVERIFIABLE` — required evidence is missing;
- `DEGRADED` — an explicit recovery conformance failure exists.

A historical LRD-01D drift identity is bound for provenance only. It cannot turn stale or missing
current evidence green.

## 6. Security / epistemic boundaries

LRD-01E grants no:

- Canonical Case Ledger write authority;
- Gold mutation authority;
- key generation/storage authority beyond caller-supplied runtime signer primitives;
- trust-set promotion or revocation authority;
- backup/recovery truth separate from DR-02;
- Product persistence authority;
- release/tag authority;
- human, independent, archival or security certification authority.

Unknown schema fields, identity substitutions, cross-case scope, revoked proofs, unchained trust
sets, tampered escrow bytes, recovery manifest/report mismatch and future timestamps fail closed.

## 7. Acceptance

The exact candidate must prove:

1. historical proof verification before renewal;
2. trust-set chain binding and ACTIVE-only current signing;
3. revoked historical proof cannot be renewed;
4. exact subject/purpose continuity;
5. strict content-addressed renewal evidence;
6. actual all-artifact escrow migration to a distinct storage profile;
7. source tamper and identity change fail closed;
8. target reread is required by the reused migration primitive;
9. DR-02 report/manifest/case binding;
10. fresh, stale, missing and failed health states;
11. future-dated evidence and cross-case substitution fail closed;
12. LRD-01D historical PASS cannot substitute for current evidence;
13. Ruff, strict MyPy, focused/adversarial tests, full regression and security/policy gates;
14. exact-head CI, guarded merge, exact resulting-main validation and unchanged v1.0.1 baseline;
15. canonical closure evidence merged to GitHub.

## 8. Non-claims

LRD-01E does not claim post-quantum cryptography, HSM/WORM custody, automatic key rotation,
external geo-redundancy, deterministic external-provider rerun, continuous monitoring, independent
certification or a new release.

## 9. Next slice

No later LRD slice is authorized by this document. Further long-range work requires evidence from
01A-01E and the live canonical roadmap; absence of an explicit approved next slice is not filled by
inference.
