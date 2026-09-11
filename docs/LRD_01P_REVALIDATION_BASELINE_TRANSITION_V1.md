# LRD-01P — Revalidation Baseline Transition v1

Status: **IMPLEMENTATION / VALIDATION IN PROGRESS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ 5a2e802366989377afad8d102ec789e21843ebde`

This document is a stage contract/evidence map only. The sole engineering-process authority remains
`docs/WORKING_PRINCIPLES.md`.

## Problem

LRD-01M deterministically decides whether a prior replay baseline is unchanged, requires fresh
revalidation, or is unverifiable. LRD-01N binds that decision to exact LRD-01K replay evidence.
LRD-01O preserves one exact verified replay state as an immutable/content-addressed baseline capsule.

The remaining gap is the transition between those independently valid objects. There is no
machine-verifiable record proving that one exact prior LRD-01O baseline was either reused or replaced
only by the exact candidate that successfully satisfied 01M/01N. Without that contract, a future
operational workflow would have to decide outside the evidence model when a candidate becomes the
next baseline. That would create an unverified promotion boundary.

## Existing authority reused

LRD-01P creates no parallel Product, replay, storage or release authority.

- `RuntimeIdentity` v3 remains execution-identity authority.
- LRD-01M remains change/invalidation authority.
- LRD-01K remains cross-environment replay/provenance authority.
- LRD-01N remains revalidation-fulfilment authority.
- LRD-01O remains verified baseline-capsule authority.
- Canonical Case Ledger remains the only writable Product case-history SSOT.

## Selected design

`ReplayRevalidationBaselineTransitionV1` is a content-addressed verification record binding:

1. exact prior LRD-01O baseline digest and repository SHA;
2. exact LRD-01M decision digest;
3. exact LRD-01N fulfilment digest;
4. candidate fingerprint, repository SHA and RuntimeIdentity digest;
5. candidate replay-report digest when fresh replay evidence exists;
6. transition state and explicit blocking violations;
7. exact resulting LRD-01O baseline digest when a baseline is reusable or advances;
8. one transition digest over the complete record.

The transition evaluator always recomputes the supplied 01M decision and 01N fulfilment from the
exact prior baseline and candidate evidence before producing a transition.

## Transition states

- `BASELINE_REUSED` — 01M is exactly `UNCHANGED`, 01N is exactly `BASELINE_REUSABLE`, no
  replacement replay is accepted, and the resulting baseline digest is exactly the prior baseline
  digest.
- `BASELINE_ADVANCED` — 01N is exactly `REVALIDATED`; the evaluator rebuilds a fresh
  `ReplayRevalidationBaselineV1` from the exact candidate RuntimeIdentity/fingerprint/replay report,
  and the transition binds its new baseline digest.
- `REVALIDATION_REQUIRED` — no fresh acceptable replay evidence exists; no resulting baseline is
  produced.
- `REVALIDATION_FAILED` — replay evidence exists but does not satisfy the semantic replay boundary;
  no resulting baseline is produced.
- `UNVERIFIABLE` — upstream evidence cannot justify a transition; no resulting baseline is produced.

A blocked candidate never becomes a baseline merely because a transition record exists.

## Meaning of baseline advance

`BASELINE_ADVANCED` means only that exact candidate evidence is eligible to serve as the next
revalidation baseline within this LRD evidence chain. It is not a Product truth promotion, release,
Gold/policy/trust-root change, certification, persistence operation, provider write, or latest-pointer
mutation.

LRD-01P deliberately does not persist a mutable "latest baseline" reference. Exact capsule bytes may
later be stored through the already-existing LRD-01O/LRD-01C contracts, but persistence and
operational selection remain outside this stage.

## Security and authority boundary

LRD-01P is verification-only. It grants no:

- scheduler/cron or workflow-dispatch authority;
- Product or Canonical Case Ledger write authority;
- release/tag/publication authority;
- storage/provider write, retention or deletion authority;
- mutable latest-baseline/persistence authority;
- Gold, policy or trust-root promotion authority;
- independent/security/regulatory certification authority.

The dedicated workflow is read-only and has no `schedule:` trigger. Provider-preservation backlog
remains deferred and no AWS/provider activation is part of this stage.

## Validation

Focused/adversarial coverage must prove at least:

- unchanged candidate reuses the exact prior baseline identity;
- changed + exact verified replay advances to one newly rebuilt exact LRD-01O baseline;
- the advanced baseline can immediately serve as the next 01M baseline and makes the same candidate
  `UNCHANGED`;
- missing replay leaves a changed candidate `REVALIDATION_REQUIRED` with no resulting baseline;
- semantic drift leaves the transition `REVALIDATION_FAILED` with no resulting baseline;
- prior-baseline, decision, fulfilment, candidate RuntimeIdentity/repository SHA and replay-SHA
  substitutions fail closed;
- stale decision/fulfilment evidence cannot advance a different candidate;
- authority injection, unknown fields and transition-digest tampering fail closed.

Required regressions include LRD-01M, LRD-01N, LRD-01O, LRD-01K and periodic revalidation. Repo-wide
security, policy, supply-chain and regression gates remain mandatory.

## Definition of Done

LRD-01P may become **CLOSED / ENGINEERING PASS** only after one fresh exact implementation line:

1. proves deterministic prior-baseline-to-resulting-baseline transition identity;
2. proves 01M decision and 01N fulfilment are recomputed from exact upstream evidence;
3. proves unchanged state can only reuse the exact prior baseline;
4. proves only exact `REVALIDATED` evidence can produce a newly rebuilt 01O baseline;
5. proves REQUIRED/FAILED/UNVERIFIABLE states cannot produce a resulting baseline;
6. passes focused/adversarial tests, Ruff, strict MyPy and required upstream regressions;
7. passes the complete required exact-SHA repository CI set;
8. retains unchanged PR head/base before guarded merge;
9. is merged using the unchanged validated head;
10. completes terminal post-merge validation on resulting `main`;
11. leaves historical `v1.0.1` tag object, target and published release unchanged;
12. receives canonical closure evidence through a fresh closure SHA and resulting-main validation.

## Non-claims

Engineering PASS for 01P will prove transition semantics and exact evidence binding only. It will not
prove that a scheduler is active, that a latest-baseline pointer is durably persisted, that workflow
artifacts survive their configured retention period, that any provider storage is activated, that a
real case has survived elapsed years, or that an independent external reviewer/security auditor has
certified the system.
