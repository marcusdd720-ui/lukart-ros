# LRD-01Q — Revalidation Baseline Lineage v1

Status: **IMPLEMENTATION / VALIDATION IN PROGRESS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ aee5e2288e7b9009711558fba8ce7dc6783a519a`

This document is a stage contract/evidence map only. The sole engineering-process authority remains
`docs/WORKING_PRINCIPLES.md`.

## Problem

LRD-01O preserves one exact verified replay state as an immutable baseline capsule and LRD-01P
proves one exact transition from a prior baseline to either the same baseline, a freshly verified
replacement, or a blocked state. The remaining gap is longitudinal selection across more than one
transition.

A set of individually valid transition records is insufficient to determine one current verified
baseline if records can be reordered, replayed, forked or attached to stale parents. A future
operational workflow must not invent its own "latest" rule outside the evidence model.

## Existing authority reused

LRD-01Q creates no parallel replay, Product, storage or release authority.

- LRD-01O remains verified baseline-capsule authority.
- LRD-01P remains single-transition authority.
- LRD-01M remains change/invalidation authority.
- LRD-01N remains revalidation-fulfilment authority.
- LRD-01K remains cross-environment replay/provenance authority.
- Canonical Case Ledger remains the only writable Product case-history SSOT.

## Selected design

`ReplayRevalidationBaselineLineageV1` is a self-contained, immutable/content-addressed lineage that
contains:

1. the complete canonical genesis LRD-01O baseline capsule;
2. an ordered sequence of complete canonical LRD-01P transition records;
3. exact resulting LRD-01O baseline evidence for every successful transition;
4. ordered transition digests;
5. deterministic transition/success/advance/blocked counters;
6. one derived current baseline digest and repository SHA;
7. one lineage digest over the complete canonical record.

The lineage never accepts a caller-supplied "current" baseline. It derives the current baseline from
the genesis capsule plus the exact ordered transition sequence.

## Lineage rules

For every entry:

- `prior_baseline_digest` must equal the currently derived baseline digest;
- `prior_repository_sha` must equal the currently derived baseline repository SHA;
- transition digests must be unique within one lineage;
- `BASELINE_REUSED` must preserve the exact current baseline bytes and repository SHA;
- `BASELINE_ADVANCED` must carry the exact resulting LRD-01O capsule bound by the transition and
  advances the current baseline to that capsule;
- `REVALIDATION_REQUIRED`, `REVALIDATION_FAILED` and `UNVERIFIABLE` may be recorded as attempts but
  cannot carry resulting baseline evidence and cannot change the current baseline;
- fork, stale-parent, duplicate transition, reorder, nested transition tamper, resulting-baseline
  substitution or summary tamper fails closed.

`append()` returns a new lineage object. The prior lineage object and digest remain unchanged.

## Meaning of current baseline

The derived `current_baseline` is the most recent baseline justified by the exact ordered lineage. It
is not a mutable pointer, database row, branch ref, release alias or storage location. Selecting a
lineage as operationally authoritative and durably persisting that selection remain outside 01Q.

## Security and authority boundary

LRD-01Q is verification-only. It grants no:

- scheduler/cron or workflow-dispatch authority;
- mutable latest-baseline pointer authority;
- persistence or database write authority;
- Product or Canonical Case Ledger write authority;
- release/tag/publication authority;
- storage/provider write, retention or deletion authority;
- Gold, policy or trust-root promotion authority;
- independent/security/regulatory certification authority.

The dedicated workflow is read-only and has no `schedule:` trigger. Provider preservation remains
`DEFERRED` under `docs/IDEAS_BACKLOG.md`; 01Q does not activate AWS or any other provider.

## Validation

Focused/adversarial coverage must prove at least:

- empty lineage derives the exact genesis baseline;
- blocked → advanced → reused sequence derives the exact advanced baseline;
- append is immutable and produces a fresh lineage identity;
- reordering fails as stale-parent/fork;
- explicit forked prior baseline fails closed;
- duplicate transition replay fails closed;
- advanced transition requires exact resulting baseline bytes;
- blocked transition rejects resulting-baseline injection;
- nested transition, derived-summary and lineage-digest tampering fail closed;
- authority/unknown-field injection fails closed;
- canonical round-trip reproduces exact lineage identity.

Required regressions include LRD-01P, LRD-01O, LRD-01N, LRD-01M, LRD-01K and periodic
revalidation. Repo-wide security, policy, supply-chain and regression gates remain mandatory.

## Definition of Done

LRD-01Q may become **CLOSED / ENGINEERING PASS** only after one fresh exact implementation line:

1. proves deterministic current-baseline derivation from genesis plus ordered transition evidence;
2. proves fork/stale-parent/reorder/duplicate transition rejection;
3. proves blocked attempts cannot change the derived baseline;
4. proves only exact successful transition evidence can retain or advance the baseline;
5. proves prior lineage identity remains immutable after append;
6. passes focused/adversarial tests, Ruff, strict MyPy and required upstream regressions;
7. passes the complete required exact-SHA repository CI set;
8. retains unchanged PR head/base before guarded merge;
9. is merged using the unchanged validated head;
10. completes terminal post-merge validation on resulting `main`;
11. leaves historical `v1.0.1` tag object, target and published release unchanged;
12. receives canonical closure evidence through a fresh documentation-only closure SHA and
    resulting-main validation.

## Non-claims

Engineering PASS for 01Q will prove immutable lineage semantics and deterministic current-baseline
derivation only. It will not prove that a scheduler is active, that a mutable/durable latest-baseline
pointer exists, that workflow artifacts survive configured retention, that a lineage is operationally
selected or durably persisted, that provider storage is activated, that real elapsed years have
passed, or that an independent external reviewer/security auditor certified the system.
