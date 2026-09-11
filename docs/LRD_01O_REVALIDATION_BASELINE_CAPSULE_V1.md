# LRD-01O — Replay Revalidation Baseline Capsule v1

Status: **CLOSED / ENGINEERING PASS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ 7899fad3efb0c530748333145855b9dbbd52304c`

This document is a stage contract/evidence map only. The sole engineering-process authority remains
`docs/WORKING_PRINCIPLES.md`.

## Problem

LRD-01M correctly fails closed when the baseline revalidation fingerprint or its exact
RuntimeIdentity is missing. LRD-01N can prove that a required replay was fulfilled by exact
candidate-bound LRD-01K evidence. LRD-01K itself produces real cross-environment aggregate replay
evidence. However, there is no self-contained immutable object that preserves the exact verified
replay state needed to become the next LRD-01M baseline.

Without such an object, an operational workflow would have to reconstruct a previous baseline from
mutable/current facts, silently assume that unchanged fields were unchanged, or return
`UNVERIFIABLE`. Reconstructing old identity from current state would violate Evidence Before
Conclusion.

## Existing authority reused

LRD-01O creates no new replay, semantic, storage or Product authority.

- `RuntimeIdentity` v3 remains execution-identity authority.
- LRD-01M remains change/invalidation authority.
- LRD-01K remains cross-environment replay/provenance authority.
- LRD-01N remains revalidation-fulfilment authority.
- LRD-01C `ArtifactEscrowBackendV1` remains the replaceable exact-byte storage contract; backend
  location is not evidence identity.
- Canonical Case Ledger remains the only writable Product case-history SSOT.

## Selected design

`ReplayRevalidationBaselineV1` is a self-contained, content-addressed verification capsule. It binds:

1. exact full repository SHA;
2. exact replay repository SHA, which must equal the repository SHA;
3. complete replay-capable RuntimeIdentity v3;
4. exact LRD-01M `ReplayRevalidationFingerprintV1` bound to that RuntimeIdentity;
5. full independently verified LRD-01K aggregate report;
6. exact LRD-01K report digest;
7. an exact content digest over the complete capsule body.

A baseline capsule is constructible only when every LRD-01K receipt is `VERIFIED` and its existing
classification is one already acceptable to the 01K/01N replay boundary:
`EXACT_ENVIRONMENT_REPLAY`, `CROSS_ENV_SEMANTICALLY_EQUIVALENT`, or
`PRESENTATION_ONLY_DRIFT`. Semantic drift, incompatible or unverifiable replay evidence cannot seed
a future baseline.

The verified LRD-01K plan must match the fingerprint for all shared identities: LRD-01I preserved
bundle, SSC-02 manifest, environment-profile matrix, replay policy, migration registry,
canonicalization profile and crypto profile. The fingerprint continues to carry storage-profile
identity under 01M authority.

## Escrow compatibility

`publish_revalidation_baseline_v1` serializes exact canonical UTF-8 JSON bytes and publishes them
through the existing `ArtifactEscrowBackendV1` byte-store contract. The returned
`EscrowBlobIdentityV1` is content-addressed by exact bytes and size.

`restore_revalidation_baseline_v1` performs the inverse operation: the backend first re-verifies raw
blob size/hash, then the capsule parser re-verifies every nested identity and replay report, and
finally rejects non-canonical JSON bytes. This permits alternate-storage migration through existing
LRD-01C primitives without making storage location part of baseline identity.

No new escrow manifest role, provider backend or storage authority is introduced by 01O.

## Future invalidation handoff

`invalidation_inputs()` exposes exactly the verified fingerprint and RuntimeIdentity that were
preserved in the capsule. They can be supplied unchanged as the baseline arguments to
`evaluate_revalidation_requirement_v1` for a future candidate.

The baseline capsule does not itself select the next candidate, execute replay or promote a new
baseline. A later operational composition may consume this verified object, but it must not
reconstruct or mutate its contents.

## Security and authority boundary

LRD-01O is verification-only. It grants no:

- scheduler/cron or workflow-dispatch authority;
- Product or Canonical Case Ledger write authority;
- Gold, policy or trust-root promotion authority;
- release/tag/publication authority;
- provider credentials or provider activation authority;
- storage durability, retention-policy or deletion authority;
- key-custody or certification authority.

The dedicated workflow is read-only and has no `schedule:` trigger. Existing provider-preservation
backlog remains deferred and no AWS/provider activation is part of this stage.

## Validation

Focused/adversarial coverage proves at least:

- canonical content-addressed build/parse round trip;
- exact publish/read through existing filesystem escrow;
- alternate-store migration without identity change;
- restored capsule supplies exact usable LRD-01M baseline inputs;
- repository SHA, replay SHA and RuntimeIdentity substitution fail closed;
- fingerprint/RuntimeIdentity substitution fails closed;
- LRD-01K content tampering fails closed;
- report-plan/fingerprint substitution fails closed;
- semantic-drift replay cannot seed a baseline;
- authority injection and capsule-digest tampering fail closed.

Required regressions include LRD-01M, LRD-01N, LRD-01K and LRD-01C. Repo-wide security, policy,
supply-chain and regression gates remain mandatory.

## Definition of Done

LRD-01O is closed only after one fresh exact implementation line:

1. proves deterministic self-contained baseline identity;
2. proves exact RuntimeIdentity/fingerprint/replay-report/repository-SHA binding;
3. proves only verified semantically acceptable LRD-01K evidence can seed a baseline;
4. proves exact-byte publish/restore through existing escrow without storage-location authority;
5. proves restored evidence can drive a future 01M invalidation decision;
6. passes focused/adversarial tests, Ruff, strict MyPy and required upstream regressions;
7. passes the complete required exact-SHA repository CI set;
8. retains unchanged PR head/base before guarded merge;
9. is merged using the unchanged validated head;
10. completes terminal post-merge validation on resulting `main`;
11. leaves historical `v1.0.1` tag object, target and published release unchanged;
12. receives canonical closure evidence through a fresh closure SHA and resulting-main validation.

## Canonical closure evidence

Implementation candidate: `c56beaa0083479b369b8b1a3775f7d4a9942eb19`.

Implementation PR: `#238`, merged only after the unchanged head/base guard. The exact candidate
completed the full pull-request qualification set with **37/37 SUCCESS**. During qualification one
LRD-01K frozen-OCI job encountered an external Docker Hub connection reset while pulling the
BuildKit image; all preceding 01K environment, aggregation and authority checks had succeeded. The
failed job was rerun on the unchanged candidate SHA and completed successfully, with no code,
workflow or gate weakening and no replacement candidate commit. The resulting implementation main
is `ec615c31bf10cf493254cb8dcd14b60095e9bc11`.

Post-merge qualification of that exact resulting main completed with **33/33 push workflows
SUCCESS**, with no failed, queued or in-progress push workflow before this closure record was
created.

The closure record is intentionally a fresh documentation-only change based on that validated
resulting main and must itself pass fresh exact-SHA CI, guarded merge, and resulting-main post-merge
validation before this status is treated as canonical.

The historical `v1.0.1` tag object remains
`9f7c0b28f766c8921e63b1d517fefcc96aa991d4`, targeting
`802013c4d0e53dc12306a97e1877ebba86af64a7`; the published `MVROS 1.0.1` release remains bound to
that target. No release or tag mutation is part of LRD-01O closure.

No GitHub Actions run IDs are used as evidence authority. Workflow identity, exact commit identity,
terminal status and aggregate counts are sufficient for this closure record and avoid encoding
incidental run-number values as durable identity.

## Non-claims

Engineering PASS for 01O proves a portable verified baseline representation and exact-byte escrow
compatibility. It does not prove that a production baseline has already been durably retained for
any elapsed period, that future changes automatically consume the latest capsule, that 01K
artifacts are preserved beyond their configured workflow retention, that a scheduler is active, or
that real cases survived 10+ elapsed years. It does not activate provider storage, prove
physical/geographic media separation, perform disaster recovery, establish key custody, or provide
independent/security/regulatory certification.
