# CASE-OPS-04 — Redundant Offline Recovery Set & Restore Drill v1

Status: `CASE-OPS-04 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-03 — Offline Local Recovery Capsule & Key Recovery v1`
Deployment boundary: `LOCAL / NON-CLOUD`

## Problem and measured gap

CASE-OPS-03 closes the byte-complete recovery and historical-key-loss gap for one authenticated recovery capsule, but the capsule and its passphrase remain a correlated single recovery path. Loss of the only capsule or the only passphrase makes the encrypted evidence unrecoverable. Physical co-location of the capsule with the live workstation also leaves disk loss, theft or local ransomware as a common-mode failure.

The next improvement must reduce those single points without moving real case data to a cloud provider, inventing threshold cryptography, introducing another case-history authority or pretending that public CI can certify real physical custody.

## Evidence and alternatives

Existing controls already provide:

- exact ciphertext/provenance snapshot identity;
- passphrase-authenticated Scrypt + AES-256-GCM key wrapping;
- historical and active key recovery after evidence-key rotation;
- fail-closed capsule verification and restore;
- no plaintext evidence or raw key-file persistence by the recovery capsule;
- exact tenant/case authorization.

Material alternatives:

1. **No change / one capsule.** Rejected: one lost capsule or passphrase remains catastrophic.
2. **Custom Shamir/threshold-secret implementation.** Rejected for this stage: it adds custom cryptographic code, share lifecycle and operator complexity before simpler existing primitives are exhausted.
3. **OS/TPM/HSM-bound recovery authority.** Rejected as the portable v1 baseline: replacement-machine recovery becomes platform/hardware/custody dependent and no HSM/TPM infrastructure is currently an approved deployment dependency.
4. **Two independently wrapped CASE-OPS-03 capsules on two separate recovery devices, each separate from the live evidence device.** Selected. It reuses already validated crypto and makes either member independently sufficient for recovery (`1-of-2`) while detecting common-device placement at creation/verification time.

## Trust and authority boundary

The Canonical Case Ledger remains the only authoritative writable SSOT for case history. CASE-OPS-04 does not write CCL history, redefine CASE-OPS-03 capsule semantics, create a second evidence store authority or promote any epistemic FACT.

A recovery-set record is digest-only operational recovery evidence. It contains no raw evidence, raw key bytes, passphrase, source path or destination path. Losing the recovery-set record does not make either underlying CASE-OPS-03 capsule unreadable; each capsule remains independently verifiable through the CASE-OPS-03 contract.

## Recovery-set contract

The v1 profile is fixed as `REDUNDANT_1_OF_2_DISTINCT_DEVICE_V1`:

- exactly two members, canonical slots `A` and `B`;
- recovery threshold `1` — either exact member is sufficient;
- both members bind the exact same CASE-OPS-03 snapshot digest;
- capsule identities must be distinct;
- key-envelope identities must be distinct, proving independent wrapping rather than two byte-copies of one envelope;
- passphrases supplied at set creation/verification must be different;
- member A and member B must reside on distinct filesystem device identifiers;
- at creation, both recovery devices must also differ from the live private-evidence device.

Python `os.stat(...).st_dev` is used only as a local runtime observation of the filesystem device. It is not persisted into the content identity because it is platform/runtime metadata, not a durable cryptographic device identity.

Unknown set fields, schema/profile/device policy, threshold, member count, slot ordering or inconsistent member/snapshot identity fail closed.

## Creation semantics

Creation performs device/passphrase/destination preflight before writing. Each member is then created through the existing CASE-OPS-03 `create_recovery_capsule()` path with the same verified live store but an independent passphrase and independent randomized key envelope.

Both members are first created under hidden staging names on their target devices. Their exact snapshot digests must match. Only after both members are valid are they published to the requested final paths. Any detected mismatch or creation/verification failure aborts the set and removes artifacts created by the failed operation on a best-effort basis.

Cross-device publication cannot be a single filesystem transaction. Therefore the authoritative statement is narrower: a set is issued only after both final members are present and re-verified; partial files from a failed operation are never returned as a valid recovery set.

## Single-member recovery

`restore_recovery_set_member()` intentionally needs only:

- the digest-only recovery-set identity;
- one selected member capsule;
- that member's passphrase;
- exact tenant/case authorization.

The other capsule and the other passphrase are not required. This is the concrete availability improvement over CASE-OPS-03: loss of one recovery member or one of the two independent passphrases no longer destroys the only recovery path, provided the surviving member/passphrase pair remains available.

The function verifies the selected member's exact capsule, snapshot and key-envelope identities before delegating to CASE-OPS-03 restore.

## Restore drill

The CASE-OPS-04 drill first verifies both members and their current distinct-device placement. It then restores the exact snapshot independently from member A and member B into two empty restore targets.

A PASS drill receipt binds only:

- schema/profile;
- exact case-scope digest;
- exact recovery-set identity;
- exact snapshot digest;
- restored member count;
- digest of the recovered key identities (key IDs/versions only, never key bytes);
- result `PASS`.

The receipt contains no path, passphrase, raw key material or plaintext evidence.

## Failure and adversarial requirements

Synthetic tests must cover at least:

- same snapshot with distinct capsule/key-envelope identities;
- independent passphrase enforcement;
- same-device rejection before set publication;
- successful restore from one member after the other capsule is removed;
- wrong passphrase rejection;
- tampered member rejection;
- cross-case substitution rejection;
- unknown recovery-set fields rejection;
- full two-member restore drill;
- no passphrase/raw-key/path leakage in set or drill receipt.

CASE-OPS-01/02/03 security, provenance, derivation and runtime-bridge regressions remain mandatory.

Public GitHub Actions uses synthetic evidence, synthetic keys and synthetic passphrases only. Device-separation positive paths in CI use an injected test probe to exercise the policy logic on one hosted runner filesystem. That is engineering verification of the control logic, **not evidence that two real removable devices or independent custodians exist**.

## Security and residual risk

CASE-OPS-04 reduces two single points: one physical recovery copy and one recovery passphrase. It does not make compromise impossible. Two recoverable members also create two attackable capsule/passphrase pairs, so the operational rule remains separation of both media and secrets.

The largest remaining failure mode is correlated custody failure: both devices and both passphrases can still be lost, stolen or compromised together. Real independent-site or independent-custodian evidence requires an actual operator deployment/drill and cannot be manufactured by repository CI.

No HSM, TPM, WORM, geographic durability, independent escrow, human-independent custody, ransomware-proof media, cloud durability or external/security certification is claimed.

## Long-horizon contract

CASE-OPS-04 is additive. CASE-OPS-01/02 evidence identities, CASE-OPS-03 capsules and CCL history remain immutable. Recovery-set records are content-addressed operational projections over exact capsule identities; they are not authorities.

A future stage may add an OS/HSM-backed wrapping adapter, independent-site custody evidence or a versioned threshold-custody profile only after a measured operational need and a separately validated migration path. Unknown future profiles fail closed rather than being silently treated as v1-compatible.
