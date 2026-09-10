# CASE-OPS-08 — Private Derivation Migration Readiness & Operator Tooling v1

Status: `CASE-OPS-08 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-07 — Environment-Bound OCR Replay Verification v1`
Deployment boundary: `PRIVATE LOCAL / NON-CLOUD`

## Problem / measured gap

CASE-OPS-02 derivation receipts correctly bind `config_digest`, but deliberately do not embed the
canonical configuration bytes. For the fixed CASE-OPS-07 OCR v1 profile those bytes are known from
the current contract. For deterministic UTF-8 derivations, however, `max_input_bytes` is a bounded
operator parameter and historical non-default values cannot be reconstructed from a one-way digest
alone.

That is safe for integrity but incomplete for 10+ year migration operations: an operator can prove
that a candidate configuration is the one historically bound by a receipt, but there was no
bounded tool that inventories all runtime-supported derivations, distinguishes reconstructable
profiles from unresolved ones, and fails closed on unknown migration paths.

There is no evidence that a new receipt schema or a destructive in-place migration is currently
required.

## Alternatives considered

1. No change — rejected because migration readiness remains manual and non-measurable.
2. Rewrite historical v1 receipts to embed config bytes — rejected because it mutates immutable
   provenance identity.
3. Introduce a v2 derivation receipt now and duplicate every historical receipt — rejected because
   there is no new runtime semantic requirement and duplicate derivations would create selection
   ambiguity in the current verified projection contract.
4. Guess historical configuration from common/default values — rejected because digest identity is
   intentionally one-way and ambiguity must fail closed.
5. Add a content-addressed compatibility/readiness inventory with verified operator-supplied config
   recovery and explicit unknown-profile status — selected as the smallest justified solution.

## Contract

`PrivateDerivationMigrationReadinessV1` starts from
`load_verified_projection(store)`. Therefore the inventory is permitted only for an already valid,
case-scoped, bounded CASE-OPS runtime projection. Every derivation is reloaded by exact receipt
digest through the existing CASE-OPS-02 verifier before classification.

The report binds:

- private case-scope digest;
- exact verified projection identity;
- content-addressed migration-policy identity;
- every exact derivation receipt and semantic derivation identity;
- exact source and derived evidence identities;
- replay class, transform id/version and config digest;
- config-resolution status;
- compatibility status and required migration action;
- canonical config bytes only when those bytes are proven by the current profile contract or by an
  operator candidate whose canonical digest exactly matches the historical receipt.

The report contains no evidence text, source reference, local path, key material, credential or CCL
write capability.

## Supported v1 classifications

### Deterministic UTF-8 LF view

Current profile:

- transform `lukart.utf8-lf-text-view`;
- version `1`;
- replay class `DETERMINISTIC`;
- config fields exactly `encoding`, `newline`, `bom`, `nul`, `max_input_bytes`;
- `max_input_bytes` must remain within the CASE-OPS-02 bound.

The default current configuration is reconstructed directly and must hash to the receipt's
`config_digest`. A non-default historical digest becomes `CONFIG_RECOVERY_REQUIRED` /
`SUPPLY_VERIFIED_CONFIG`. The operator may supply a canonical JSON candidate; it is accepted only
if the field/value contract is valid and its exact digest equals the historical digest. A wrong
candidate fails the operation rather than producing a weaker report.

### Tesseract OCR v1

The exact CASE-OPS-07 profile is classified `REPLAY_READY_ENVIRONMENT_BOUND` only when transform,
version, replay class and the fixed `pol+eng` / PSM 6 / stdin config digest all match. This does not
promote OCR to deterministic replay.

### Unknown or changed profile

Any other verified transform/version/replay/config combination is
`EXPLICIT_MIGRATION_REQUIRED` / `DEFINE_VERSIONED_MIGRATION`. A config candidate cannot authorize
an unknown profile. The next migration must be designed and versioned explicitly against its real
semantics; CASE-OPS-08 does not manufacture that path.

## Operator behavior

`scripts/private_derivation_migration.py` requires:

- explicit `--confirm-private-local-case`;
- exact tenant/case scope;
- read-only evidence authorization;
- local evidence keys outside the public repository;
- optional `--config-candidate RECEIPT_DIGEST JSON_FILE` bindings;
- an immutable report target outside the public repository.

Exit `0` means the verified inventory is `READY`. Exit `2` means the report is valid but one or more
explicit operator/migration actions remain. Exit `1` means verification itself failed closed.

## Security / migration invariants

- historical receipt bytes and identities are never rewritten;
- CCL remains the sole authoritative writable case-history SSOT;
- no migration can be inferred from a matching-looking transform name;
- an operator candidate is evidence only after exact canonical config-digest equality;
- unknown receipt/profile/schema/path remains fail-closed through the underlying CASE-OPS verifier;
- report output is immutable (`0600`, exclusive create), idempotent only for identical bytes, and
  must be outside the public repository;
- public CI uses synthetic evidence only;
- no cloud/AWS/provider dependency is introduced.

## Validation

Focused/adversarial tests must prove:

- default deterministic UTF-8 and exact OCR v1 classify READY without receipt mutation;
- non-default deterministic config is unresolved without exact config bytes;
- a verified matching candidate recovers readiness;
- wrong/unknown candidate fails closed;
- unknown transform becomes explicit versioned-migration work, never implicit PASS;
- immutable report output contains no evidence text/source slot and cannot enter the public repo;
- CASE-OPS-02 runtime bridge, derivation, CASE-OPS-07 OCR replay and private pilot remain regression
  dependencies.

Full repository regression, lint/type checks, security/policy gates, exact-SHA CI, guarded merge and
post-merge validation remain mandatory before engineering closure.

## Residual risk / next boundary

CASE-OPS-08 cannot recover configuration bytes that were never preserved and whose digest does not
match a known profile; cryptographic preimage recovery is neither possible nor desirable. Such a
receipt therefore remains explicitly unresolved until an operator supplies the exact historical
config or a separately designed versioned migration handles it.

The readiness report is an operator/review artifact, not a second provenance authority and not a
replacement for the immutable derivation receipt. A future receipt revision should embed or
content-address the complete canonical config at creation time only when a real semantic/version
change justifies that new schema; historical v1 receipts must remain immutable.

This stage does not claim an executed real-data migration, independent review, external/security
certification, cloud durability or release issuance.
