# LRD-01M — Change-Triggered Replay Invalidation & Revalidation Requirement v1

Status: **CLOSED / ENGINEERING PASS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ 2a138055fd4f50126ba5c90e3821cbd24ad283be`

This document is a stage contract/evidence map only. The sole engineering-process authority remains
`docs/WORKING_PRINCIPLES.md`.

## Problem

The active long-range roadmap requires historical replay to remain demonstrably verifiable after
changes in Python, providers/models, storage and build infrastructure. LRD-01K records exact
cross-environment replay provenance, while LRD-01L detects stale or missed replay intervals.
However, LRD-01L evaluates elapsed time only: a replay can still be `CURRENT` immediately after a
material execution/replay/storage identity changes.

A prior PASS therefore needs a deterministic invalidation rule. Without one, freshness by age can
be mistaken for freshness against the current execution assumptions.

## Existing authority reused

LRD-01M creates no new provider, model, dependency, storage, migration, crypto or replay authority.
It composes identities already owned elsewhere:

- `RuntimeIdentity` v3: code, schema, config, corpus, provider/plugin inventories, inputs/evidence,
  dependency lock, Python implementation/version, platform, project version and build backend;
- LRD-01I: preserved survivability-bundle identity;
- SSC-02: supply-chain continuity manifest identity;
- LRD-01K: environment-profile matrix, replay policy, migration, canonicalization and crypto
  identities;
- DR-02/LRD-01G storage-profile identities.

Where a model identity is represented by an existing provider/config/runtime binding, 01M observes
that existing identity only. It does not invent a model registry or infer a model identity from a
name, endpoint or mutable label.

## Selected design

`ReplayRevalidationFingerprintV1` is a content-addressed dependency fingerprint. Construction
requires a complete replay-capable RuntimeIdentity v3, at least two environment-profile identities
matching the cross-environment design, and at least one exact storage-profile identity. Missing or
malformed identities fail closed.

`ReplayRevalidationDecisionV1` compares one baseline fingerprint against one candidate fingerprint
and the exact RuntimeIdentity objects bound by those fingerprints. It has three states:

- `UNCHANGED` — no tracked identity changed; the change-trigger rule does not invalidate the prior
  replay evidence;
- `REVALIDATION_REQUIRED` — at least one tracked identity changed; the prior replay PASS cannot be
  reused as evidence for the candidate dependency fingerprint;
- `UNVERIFIABLE` — the required baseline/current identity evidence is incomplete, so reuse is
  forbidden rather than guessed.

The decision is itself content-addressed and records deterministic changed domains and exact changed
field names. Revalidation requirement is not a replay result: `REVALIDATION_REQUIRED` never means
that a new replay has passed.

## Change domains

Runtime changes are classified without replacing RuntimeIdentity authority: code, schema, config,
corpus, provider, plugin, input, evidence, dependency, Python, platform, project version and build
backend. LRD composition changes cover preserved bundle, SSC-02 supply chain, environment profile
matrix, replay policy, migration registry, canonicalization profile, crypto profile and storage
profile identities.

Any tracked difference invalidates reuse of the old replay PASS. The rule intentionally prefers a
false-positive revalidation requirement over a false claim that materially changed assumptions are
still covered by historical evidence.

## Security and authority boundary

LRD-01M is verification-only. It adds no:

- scheduler/cron authority or cadence selection;
- GitHub workflow dispatch/write authority;
- release/tag/publication authority;
- Product or Canonical Case Ledger write path;
- provider credentials or AWS authority;
- policy/trust-root promotion authority;
- semantic comparison authority;
- independent/human/security certification authority.

The dedicated workflow is read-only, runs only on pull request, push or manual dispatch, and
explicitly rejects an introduced `schedule:` trigger. A business/operational cadence remains outside
01M and remains governed by the existing 01L boundary.

## Adversarial acceptance

Focused coverage fails closed for at least:

- runtime identity substitution against a bound fingerprint;
- missing baseline identity;
- incomplete RuntimeIdentity inventories;
- code/provider/dependency/Python/platform/build changes;
- LRD-01I or SSC-02 identity change;
- environment/migration/canonicalization/crypto identity change;
- storage-profile change;
- missing environment/storage identity inventory;
- unknown schema/fields/change domains;
- content-digest tampering;
- authority injection into scheduler/release/Product/CCL fields.

Runtime identity, Case Replay v2, LRD-01K, LRD-01L and LRD-01G remain regression dependencies.

## Definition of Done

LRD-01M is closed only after one fresh exact implementation line:

1. proves deterministic content-addressed fingerprint and decision identities;
2. proves every tracked dependency change invalidates reuse of the prior replay PASS;
3. fails closed for missing/substituted/incomplete identity evidence;
4. preserves upstream RuntimeIdentity/LRD-01K/LRD-01L/storage authorities unchanged;
5. passes focused/adversarial tests, Ruff, strict MyPy and required upstream regressions;
6. passes the complete required exact-SHA repository CI set;
7. retains unchanged PR head/base before guarded merge;
8. is merged using the unchanged validated head;
9. completes terminal post-merge validation on resulting `main`;
10. leaves historical `v1.0.1` tag object, target and published release unchanged;
11. receives canonical closure evidence through a fresh closure SHA and resulting-main validation.

## Canonical closure evidence

Implementation candidate: `8f642a633456bae34d3ffe25a91abd6029279593`.

Implementation PR: `#234`, merged only after the unchanged head/base guard. The exact candidate
completed the full pull-request qualification set with **35/35 SUCCESS** and no terminal failure.
The resulting implementation main is `fbf7cf0241d50f7ebed0ee37f2eebc1aa8c6c538`.

Post-merge qualification of that exact resulting main completed with **31/31 SUCCESS**, with no
failed, queued or in-progress workflow run before this closure record was created. The closure
record is intentionally a fresh documentation-only change based on that validated resulting main
and must itself pass fresh exact-SHA CI, guarded merge, and resulting-main post-merge validation
before this status is treated as canonical.

The historical `v1.0.1` tag object remains
`9f7c0b28f766c8921e63b1d517fefcc96aa991d4`, targeting
`802013c4d0e53dc12306a97e1877ebba86af64a7`; the published `MVROS 1.0.1` release remains bound to
that target. No release or tag mutation is part of LRD-01M closure.

No GitHub Actions run IDs are used as evidence authority. Workflow identity, exact commit identity,
terminal status and aggregate counts are sufficient for this closure record and avoid encoding
incidental run-number values as durable identity.

## Non-claims

Engineering PASS for 01M does not mean that a replay is automatically executed after every real
change, that continuous monitoring is active, that a scheduler/cadence exists, or that historical
cases survived 10+ elapsed years. It does not prove provider durability, physical/geographic media
separation, disaster-recovery execution, external model availability, key custody, or
human/independent/security/regulatory certification.

AWS/provider durability remains outside this stage and deferred according to the live roadmap.
