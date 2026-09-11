# LRD-01 — Periodic Operational Freshness Gate v1

Status: **CLOSED / ENGINEERING PASS**  
Parent program: `continuous LRD-01`  
Implementation base: `main @ 7455e5e850caf3856198f383d8f27252ceab45bf`  
Implementation PR: `#253`  
Implementation merge: `main @ baa54871b437148250e3c5d71c5d9fe5c2a11d5c`

This document is the canonical stage-contract and closure-evidence map for the periodic operational freshness composition added under continuous LRD-01. It introduces no new LRD stage identifier. The sole engineering-process authority remains `docs/WORKING_PRINCIPLES.md`.

## Problem and measured gap

Before this change, two independently closed LRD-01 contracts could both behave correctly while still leaving an operational composition gap:

- LRD-01L could classify periodic replay evidence as `CURRENT`, `DUE`, `OVERDUE` or `UNVERIFIABLE` from an explicit cadence policy, evaluation time and immutable observation chain;
- LRD-01S could take an otherwise valid candidate through the bounded revalidation handoff and persist the resulting selection lineage through the existing LRD-01R path.

The missing seam was that LRD-01S did not itself require the latest LRD-01L freshness evidence to be acceptable before selection persistence. An operational caller could therefore compose the contracts incorrectly and attempt an otherwise valid baseline-selection handoff while periodic replay evidence was already `OVERDUE` or `UNVERIFIABLE`.

The measured gap was composition-only. No new scheduler, repository watcher, replay runner, cadence-selection policy, cloud/provider authority, storage authority, Product authority, CCL authority or release authority was required.

## Selected design

The implementation adds one bounded fail-closed wrapper:

`explicit cadence policy + evaluation time + immutable LRD-01L observations + exact candidate inputs -> LRD-01L freshness evaluation -> freshness identity checks -> existing LRD-01S handoff`

The wrapper reuses the existing authorities rather than cloning them:

- LRD-01L remains the freshness-state authority;
- LRD-01S remains the operational revalidation-handoff authority;
- LRD-01R remains the only durable selection-persistence path;
- the existing cross-environment replay verifier remains the replay-report verification authority when a replay report is supplied;
- the existing `RuntimeIdentity` and revalidation fingerprint contracts remain authoritative for candidate identity.

Only `CURRENT` and `DUE` periodic states are accepted. `DUE` remains acceptable because LRD-01L defines it as inside the warning window but not yet overdue. `OVERDUE` and `UNVERIFIABLE` fail closed before the existing LRD-01S persistence path can run.

The latest accepted periodic observation must bind to the exact candidate repository SHA and the exact LRD-01I survivability-bundle identity already present in the candidate fingerprint. If a verified replay report is supplied to LRD-01S, its verified report digest must also equal the latest periodic observation's cross-environment report identity.

## Time and cadence boundary

The freshness gate does not read wall-clock time and does not choose cadence.

Both are explicit caller inputs:

- `PeriodicReplayCadencePolicyV1` is supplied by the caller;
- `evaluated_at` is supplied by the caller;
- the immutable observation chain is supplied by the caller.

Therefore this composition cannot silently create a scheduler, cron policy, warning-window default or operational timing authority. It only verifies whether the explicit inputs satisfy the already-established LRD-01L contract.

## Fail-closed semantics

The operational freshness composition rejects the handoff when any of the following is true:

- LRD-01L cannot verify the supplied periodic observation chain;
- the computed periodic state is `OVERDUE`;
- the computed periodic state is `UNVERIFIABLE`;
- the latest periodic observation repository SHA differs from the exact candidate repository SHA;
- the latest observation LRD-01I bundle identity differs from the candidate fingerprint bundle identity;
- a supplied replay report fails the existing replay verifier;
- the verified supplied replay report digest differs from the latest periodic observation report identity;
- the delegated LRD-01S handoff rejects the candidate, replay or selection state under its existing contract.

No freshness failure is converted into a warning-only PASS and no existing threshold, invariant or trust boundary is weakened.

## Authority boundary

The periodic operational freshness gate has no:

- new LRD stage identity;
- cadence-policy selection authority;
- wall-clock read authority;
- scheduler or cron authority;
- repository watcher or repository-change-detection authority;
- replay execution or runner-orchestration authority;
- provider/cloud access authority;
- storage read/write authority;
- mutable latest/current pointer authority;
- Product write authority;
- Canonical Case Ledger write authority;
- release/tag/publication authority;
- independent persistence authority.

Selection persistence remains delegated solely to the pre-existing LRD-01S/LRD-01R path.

## Validation contract

Focused and adversarial validation covers:

- `CURRENT` periodic freshness followed by valid operational handoff;
- `DUE` periodic freshness followed by valid operational handoff;
- a fresh changed candidate that correctly proceeds through the existing handoff semantics;
- `OVERDUE` freshness rejection before persistence;
- `UNVERIFIABLE` freshness rejection before persistence;
- candidate repository-SHA substitution rejection;
- LRD-01I bundle-identity substitution rejection;
- supplied replay-report identity mismatch rejection;
- reuse of the existing replay verifier rather than accepting unverified report content;
- preservation of the existing LRD-01S authority boundaries;
- regression coverage for periodic replay revalidation, baseline selection, lineage, transition and operational handoff.

The existing LRD-01S workflow was extended rather than replaced. It validates the freshness module with frozen dependencies, Ruff, strict MyPy, focused/adversarial/full test coverage and the required upstream revalidation regressions.

## Implementation repair loop

The implementation remained within the canonical repair loop. The final candidate includes the smallest required typing repair in adversarial test code after MyPy identified a narrowing issue. No test, gate, threshold, policy or trust boundary was weakened.

Every material implementation change produced a fresh SHA. The final exact implementation candidate used for qualification and merge is:

`0d8c355e6ee896369b6626421ea9edb66d870323`

## Definition of Done

This closure is valid only when all of the following hold on live GitHub evidence:

1. the implementation composes existing LRD-01L freshness with existing LRD-01S operational handoff without introducing a parallel authority;
2. `OVERDUE` and `UNVERIFIABLE` fail closed before selection persistence;
3. accepted freshness binds the latest periodic observation to the exact candidate repository SHA and LRD-01I bundle identity;
4. any supplied replay report is independently verified and bound to the latest periodic observation report identity;
5. focused/adversarial/full validation, Ruff, strict MyPy and required upstream regressions pass;
6. the complete required pull-request workflow set succeeds on one exact fresh implementation candidate SHA;
7. the PR head/base remain unchanged at guarded merge;
8. the unchanged validated implementation head is merged;
9. the exact resulting implementation `main` reaches terminal success for the complete push workflow set with zero failed, cancelled, timed-out, queued or in-progress runs;
10. historical `v1.0.1` tag object, annotated target commit and latest published release remain unchanged;
11. this closure record is introduced by a separate documentation-only candidate branched from the exact validated implementation `main`;
12. that documentation-only candidate itself passes exact-SHA PR CI, unchanged head/base verification and guarded merge;
13. the resulting closure `main` is revalidated after merge and the `v1.0.1` invariant is verified again.

## Canonical implementation closure evidence

Implementation qualification:

- implementation PR: **#253**
- implementation PR base SHA: `7455e5e850caf3856198f383d8f27252ceab45bf`
- exact implementation candidate SHA: `0d8c355e6ee896369b6626421ea9edb66d870323`
- exact-SHA pull-request workflow qualification: **42/42 SUCCESS**
- guarded implementation merge resulting main: `baa54871b437148250e3c5d71c5d9fe5c2a11d5c`
- the exact implementation candidate is a direct parent of that merge commit
- resulting-main push workflow set: **38 total**
- resulting-main terminal success: **38/38 SUCCESS**
- resulting-main terminal negative states: **0 failure, 0 cancelled, 0 timed-out, 0 queued, 0 in-progress**

The implementation merge was therefore fully terminal before this documentation-only closure candidate was created.

## Immutable release invariant after implementation merge

Historical release identity remains unchanged:

- `v1.0.1` tag ref object SHA: `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
- annotated tag target commit: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- latest published release name: `MVROS 1.0.1`
- latest published release tag: `v1.0.1`
- release target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- invariant result after implementation merge: **UNCHANGED**

No release or tag mutation is part of this closure.

## Documentation-only closure protocol

This file is the sole change in the canonical closure candidate. The closure candidate is based on exact implementation `main @ baa54871b437148250e3c5d71c5d9fe5c2a11d5c`.

The file may become canonical only after its own exact-SHA pull-request CI is terminally successful, its head/base are rechecked unchanged, it is merged through a guarded exact-head merge, and the resulting `main` is validated again. The final post-merge and release-invariant observations are external live evidence and are not fabricated inside this pre-merge document.

## Non-claims

This closure does not claim that LUKART ROS autonomously chooses a replay cadence, reads trusted wall-clock time, watches the repository, dispatches replay, preserves provider infrastructure, proves cloud/provider durability, proves physical or geographic storage separation, performs a real disaster-recovery drill, controls key custody, modifies Product or CCL state, publishes a release, or provides independent external/security/regulatory certification.

The gate is intentionally narrow: it prevents an otherwise valid LRD-01S operational handoff from proceeding when the existing LRD-01L periodic replay evidence is no longer acceptably fresh or does not bind to the exact candidate/replay identities being handed off.
