# LRD-01N — Change-Triggered Revalidation Fulfilment v1

Status: **CLOSED / ENGINEERING PASS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ d951ff2899602c27bc5aa2b260860c88d1c12e24`

This document is a stage contract/evidence map only. The sole engineering-process authority remains
`docs/WORKING_PRINCIPLES.md`.

## Problem

LRD-01M deterministically invalidates reuse of an old replay PASS when a tracked runtime,
preserved-bundle, supply-chain, environment, replay-policy, migration, canonicalization, crypto or
storage identity changes. It deliberately does not claim that a required new replay was executed or
passed. LRD-01K independently produces content-addressed cross-environment replay evidence, but no
existing contract binds one exact LRD-01M invalidation decision to one exact candidate repository
identity and one fresh LRD-01K report.

Without that bridge, `REVALIDATION_REQUIRED` and a later replay PASS can coexist as separate facts
without machine-verifiable evidence that the latter actually fulfils the former for the same
candidate.

## Existing authority reused

LRD-01N creates no new replay, semantic-comparison, storage, provider, scheduler or release
authority.

- LRD-01M remains the only authority in this chain for deciding whether a previous replay may be
  reused after tracked identity change.
- LRD-01K remains cross-environment replay/provenance authority and LRD-01D remains semantic-drift
  authority.
- RuntimeIdentity v3 remains runtime/code/config/corpus/provider/plugin/input/evidence/dependency/
  interpreter/platform/build identity authority.
- LRD-01L remains periodic freshness/missed-drill evidence authority.
- Canonical Case Ledger remains the sole writable Product case-history SSOT.

## Selected design

`ReplayRevalidationFulfilmentV1` is an immutable, content-addressed verification envelope over exact
upstream evidence. Evaluation first recomputes the supplied LRD-01M decision from its original
baseline/candidate fingerprints and RuntimeIdentity objects. A supplied decision therefore cannot
be promoted merely because its serialized state says `REVALIDATION_REQUIRED` or `UNCHANGED`.

For a changed candidate, fulfilment additionally requires:

1. exact 40-character candidate repository SHA matching the candidate RuntimeIdentity `code_sha`;
2. exact replay repository SHA equal to that candidate SHA;
3. an LRD-01K aggregate report accepted by the standalone stdlib verifier;
4. exact equality between the report plan and candidate fingerprint for all shared identities:
   LRD-01I bundle, SSC-02 manifest, environment profile matrix, replay policy, migration registry,
   canonicalization profile and crypto profile;
5. a complete replay matrix whose every receipt has `VERIFIED` execution status and an acceptable
   existing LRD-01K classification.

The accepted classifications are `EXACT_ENVIRONMENT_REPLAY`,
`CROSS_ENV_SEMANTICALLY_EQUIVALENT` and `PRESENTATION_ONLY_DRIFT`. Presentation-only drift remains
acceptable because semantic authority belongs to LRD-01D/01K; LRD-01N does not reinterpret it.
`SEMANTIC_DRIFT`, `ENVIRONMENT_INCOMPATIBLE` and `UNVERIFIABLE` never satisfy revalidation.

Storage-profile identity is retained through the exact candidate fingerprint and can trigger 01M
invalidation, but LRD-01N does not reinterpret a replay PASS as proof of provider durability,
physical storage independence or DR execution. Those are separate authorities/evidence classes.

## Fulfilment states

The content-addressed envelope exposes exactly:

- `BASELINE_REUSABLE` — verified 01M decision is `UNCHANGED`; no replacement report is needed;
- `REVALIDATED` — verified 01M decision required revalidation and exact candidate-bound LRD-01K
  evidence is complete and semantically acceptable;
- `REVALIDATION_REQUIRED` — verified 01M decision requires revalidation but fresh exact replay
  evidence has not been supplied;
- `REVALIDATION_FAILED` — supplied LRD-01K evidence is structurally authentic but one or more replay
  receipts are not a verified acceptable result;
- `UNVERIFIABLE` — upstream 01M decision is itself unverifiable and therefore cannot be cured by a
  replay report.

Invalid schemas, digest tampering, decision substitution, candidate RuntimeIdentity substitution,
candidate/replay SHA mismatch, report tampering and report-plan/candidate-fingerprint substitution
fail closed as contract errors instead of being downgraded to PASS.

## Security and authority boundary

LRD-01N is verification-only. It grants no:

- scheduler/cron or workflow-dispatch authority;
- Product or Canonical Case Ledger write authority;
- Gold, policy or trust-root promotion authority;
- release/tag/publication authority;
- provider credentials, provider activation or AWS authority;
- storage durability, disaster-recovery or key-custody authority;
- independent/human/security/regulatory certification authority.

The dedicated workflow is read-only, uses exact candidate SHA checkout, frozen dependencies and the
repository-supported Python endpoints, and explicitly rejects introduction of a `schedule:` trigger
or write permissions.

## Validation

Focused/adversarial coverage includes at least:

- changed candidate with no new replay remains `REVALIDATION_REQUIRED`;
- exact candidate-bound complete 01K matrix becomes `REVALIDATED`;
- unchanged candidate reuses the verified baseline without manufacturing replacement evidence;
- missing baseline remains `UNVERIFIABLE`;
- candidate repository SHA / RuntimeIdentity substitution;
- stale replay SHA relabelled as candidate evidence;
- aggregate report content tampering;
- structurally valid `SEMANTIC_DRIFT` report remaining `REVALIDATION_FAILED`;
- partial replay SHA/report evidence;
- authority injection and fulfilment digest tampering;
- non-canonical repository SHA.

Required regressions include LRD-01M, LRD-01K, LRD-01L and Case Replay v2. Repo-wide security,
policy, supply-chain and regression gates remain mandatory.

## Definition of Done

LRD-01N is closed only after one fresh exact implementation line:

1. proves deterministic content-addressed fulfilment identity;
2. recomputes the exact LRD-01M decision instead of trusting its state label;
3. independently verifies the LRD-01K aggregate report;
4. binds candidate RuntimeIdentity, candidate repository SHA, replay repository SHA, candidate
   fingerprint and replay-plan identities without substitution;
5. never maps semantic drift, incompatible or unverifiable replay evidence to `REVALIDATED`;
6. passes focused/adversarial tests, Ruff, strict MyPy and upstream replay regressions;
7. passes the complete required exact-SHA repository CI set;
8. retains unchanged PR head/base before guarded merge;
9. is merged using the unchanged validated head;
10. completes terminal post-merge validation on resulting `main`;
11. leaves historical `v1.0.1` tag object, target and published release unchanged;
12. receives canonical closure evidence through a fresh closure SHA and resulting-main validation.

## Canonical closure evidence

Implementation candidate: `fdbd9ff27d72f44fe0a9d845defec79bc27e7c13`.

Implementation PR: `#236`, merged only after the unchanged head/base guard. The exact candidate
completed the full pull-request qualification set with **36/36 SUCCESS** and no terminal failure.
The resulting implementation main is `e10a50c7826253973cf874ec3fbf410b06c42221`.

Post-merge qualification of that exact resulting main completed with **32/32 push workflows
SUCCESS**, with no failed, queued or in-progress push workflow before this closure record was
created. Three additional downstream workflow-run events associated with the same SHA also
completed successfully; they are intentionally excluded from the 32/32 push-workflow metric so the
evidence count remains event-class precise.

The closure record is intentionally a fresh documentation-only change based on that validated
resulting main and must itself pass fresh exact-SHA CI, guarded merge, and resulting-main post-merge
validation before this status is treated as canonical.

The historical `v1.0.1` tag object remains
`9f7c0b28f766c8921e63b1d517fefcc96aa991d4`, targeting
`802013c4d0e53dc12306a97e1877ebba86af64a7`; the published `MVROS 1.0.1` release remains bound to
that target. No release or tag mutation is part of LRD-01N closure.

No GitHub Actions run IDs are used as evidence authority. Workflow identity, exact commit identity,
terminal status and aggregate counts are sufficient for this closure record and avoid encoding
incidental run-number values as durable identity.

## Non-claims

An engineering PASS for 01N proves the verification bridge, not continuous execution. It does not
itself schedule or dispatch replay, prove that every future real change automatically launches a new
replay, establish a business cadence, preserve workflow artifacts indefinitely, prove 10+ years of
elapsed survivability, activate provider storage, prove physical/geographic separation, perform
real disaster recovery, establish key custody, or provide independent/security/regulatory
certification.

The provider-preservation idea in `docs/IDEAS_BACKLOG.md` remains `DEFERRED` with its existing
revisit boundary. No AWS or other external provider is activated by this stage.
