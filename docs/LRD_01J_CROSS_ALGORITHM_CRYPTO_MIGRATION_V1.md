# LRD-01J — Cross-Algorithm Crypto Migration v1

Status: `IMPLEMENTATION CANDIDATE — NOT CLOSED`
Parent program: `continuous LRD-01`
Depends on: `CRY-01`, `LRD-01E`, `LRD-01F`
Measured base: `main @ 1d673e81f188317cceeb49ea5daf7172f5a4f0cf`

## 1. Problem

CRY-01 deliberately implements only Ed25519. LRD-01E proves additive renewal inside that
classical algorithm family. LRD-01F identifies `ML-DSA` and `SLH-DSA` as migration target
families but deliberately ends at `ADAPTER_REQUIRED` and requires any future adapter to bind
implementation/build provenance, parameter set, standard/errata identity, test vectors, key
lifecycle, failure modes, performance and interoperability evidence.

The remaining gap is therefore not another Ed25519 rotation. It is an additive,
fail-closed migration path from an already verified historical Ed25519 attestation to a
separately pinned post-quantum signature while preserving the historical proof unchanged.

## 2. Decision

LRD-01J implements one narrow adapter:

- family: `ML-DSA`;
- parameter set: `ML-DSA-65`;
- standard: `NIST-FIPS-204`;
- standard revision identity: `FIPS-204-final-2024-08-13`;
- errata awareness reference: `NIST-CSRC-planning-note-2026-07-31`;
- implementation: `pyca-cryptography 50.0.1`;
- dependency lock Git blob: `9c018011129dc660a1451289de3befb1f92d7280`;
- ML-DSA context: `LUKART-LRD-01J-ML-DSA-65-v1`.

The adapter is additive. It does **not** extend or rewrite `CryptoAlgorithmV1`, because the
closed CRY-01 key contract is intentionally Ed25519-specific. Historical verification remains
delegated to `CryptoTrustVerifierV1` under an externally pinned historical trust-set digest.

## 3. Trust and authority boundary

The migration sequence is:

`historical Ed25519 attestation -> CRY-01 verification at migration time -> ML-DSA-65 envelope -> dual verification`

The system does not infer that possession of an ML-DSA key makes that key trusted. The caller
must pin the exact migration-key context digest and adapter-profile digest. The key context is
verification metadata only and does not become Product, CCL, release or governance authority.

Private ML-DSA key material is supplied at runtime and is never stored by this module.

`CrossAlgorithmVerificationV1` always records:

- `automation_can_promote_trust=false`;
- `fips_validation_claim=false`;
- `independent_crypto_review_claim=false`.

A successful 01J result means only that the historical Ed25519 evidence was valid when the
migration was created and that the additive ML-DSA-65 envelope verifies under the exact pinned
migration context. It is not a FIPS validation, independent cryptographic review, HSM/key
custody claim or production cutover approval.

## 4. Stable key material versus lifecycle context

Migration evidence binds `key_material_digest`, not the full mutable lifecycle record.

Stable material identity includes:

- key ID;
- exact ML-DSA-65 public key bytes;
- allowed purposes;
- exact predecessor Ed25519 key ID;
- adapter profile digest.

The separately pinned `key_context_digest` additionally binds `ACTIVE / RETIRED / REVOKED`,
activation time and optional retirement time.

This preserves valid historical envelopes across a planned `ACTIVE -> RETIRED` transition.
A `REVOKED` context always fails closed. A retired key verifies only envelopes issued before
its `retire_at`. New signing is allowed only with `ACTIVE` migration keys.

## 5. Archival time semantics

The historical Ed25519 attestation is verified at `envelope.issued_at`, not at the later wall
clock time when the migration envelope is replayed. This is required for archival renewal:
a source attestation that was valid when migrated may later reach its planned expiry without
erasing the migration evidence.

A source attestation already expired at migration time fails closed. A migration envelope
from the future also fails closed.

## 6. Implementation and build provenance

`Mldsa65AdapterProfileV1` fixes the exact implementation version and the Git blob identity of
`uv.lock`. The adapter refuses runtime use unless `cryptography.__version__` equals the pinned
version and the backend can actually generate, sign and verify ML-DSA-65 with the expected
1952-byte public key and 3309-byte signature contracts.

`Mldsa65RuntimeProvenanceV1` records the signing runtime's:

- cryptography version;
- OpenSSL version text;
- Python implementation/version;
- platform system and machine identity.

This runtime evidence is embedded in the signed migration body. Verification may occur on a
different runtime, but that verifier must itself pass the pinned ML-DSA-65 capability check.

## 7. Pinned NIST ACVP vector evidence

The dedicated workflow checks out the public NIST ACVP server repository at exact commit:

`975de31eb83d87039ec88934fdc47d8c312b892d`

The key-generation evidence is additionally pinned to exact Git blobs:

- prompt: `f53809df5fefee2c1b80da1122885a2e0e843e32`;
- expected results: `38213cd71c20c019cc49bf140f616ed86c81ad98`;
- group: `2` (`ML-DSA-65`);
- case: `26`.

`scripts/verify_mldsa65_acvp_vector.py` verifies both blob identities, derives the public key
from the published seed using `MLDSA65PrivateKey.from_seed_bytes()`, compares the complete
1952-byte public key with the NIST expected result, reconstructs a verifier from raw public
bytes and performs a domain-separated sign/verify round trip.

This is conformance evidence only. It does not claim that the implementation is a validated
cryptographic module. Published ACVP vector coverage can itself have defects or blind spots;
01J therefore does not rely on the vector alone and adds independent adversarial mutations.

## 8. Focused and adversarial validation

The 01J suite covers at minimum:

- runtime capability and exact implementation version;
- valid additive Ed25519 -> ML-DSA-65 migration;
- strict key/envelope serialization and unknown-field rejection;
- source payload tampering;
- migration-envelope tampering;
- domain/context separation;
- private-key substitution;
- wrong externally pinned source trust set;
- planned migration-key retirement;
- migration-key revocation;
- source expiry after a valid migration;
- source expiry before migration;
- future envelope rejection;
- fixed-profile anti-downgrade/anti-reinterpretation;
- bounded sign/verify performance measurement;
- full pinned NIST ACVP ML-DSA-65 key-generation vector.

Regression explicitly re-runs CRY-01, LRD-01E and LRD-01F tests so 01J cannot obtain PASS by
weakening the closed classical or readiness boundaries.

## 9. Performance contract

The dedicated probe records maximum sign and verify latency over a small bounded sample and
requires each operation to remain below a deliberately loose `1000 ms` engineering budget on
CI. Timing is operational evidence, not semantic or cryptographic identity.

No throughput/SLA or production capacity claim follows from this bounded CI measurement.

## 10. Interoperability boundary

01J proves interoperability across the implementation's raw ML-DSA-65 key serialization:
a public key created by one object is reconstructed as a fresh `MLDSA65PublicKey` and verifies
the signature under the same domain context. The pinned NIST key-generation vector also proves
agreement with the external NIST expected public-key bytes for the selected parameter set.

`cross_implementation_interoperability_proven=false` remains explicit because 01J does not run
a second independent ML-DSA implementation. Cross-vendor/HSM interoperability requires a
separate stage and real evidence.

## 11. Non-goals

LRD-01J does not:

- replace or mutate CRY-01 Ed25519 trust sets;
- delete historical signatures;
- automatically promote an ML-DSA key to organizational trust;
- implement SLH-DSA;
- select production HSM/KMS/key custody;
- alter CCL, Product, Gold, KQM or release authority;
- claim FIPS validation, independent review, post-quantum certification or real production
  cutover;
- mutate the immutable `v1.0.1` release/tag baseline.

## 12. Definition of Done

01J can be closed only after:

1. focused/adversarial and pinned ACVP vector validation pass;
2. CRY-01/LRD-01E/LRD-01F regression passes;
3. lint/type/security/policy gates pass;
4. exact fresh candidate SHA has all required CI terminal `SUCCESS`;
5. PR head/base remain unchanged;
6. guarded merge succeeds;
7. resulting `main` completes terminal post-merge validation;
8. `v1.0.1` tag object, target and published release remain unchanged;
9. canonical closure evidence is merged and independently revalidated on resulting main.
