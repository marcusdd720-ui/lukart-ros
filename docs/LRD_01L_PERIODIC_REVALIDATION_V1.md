# LRD-01L — Periodic Replay Revalidation & Missed-Drill Detection v1

Status: **IMPLEMENTATION CANDIDATE / NOT CLOSED**  
Parent program: `continuous LRD-01`  
Measured base: `main @ 7428b400204431dc4218fc86e1c0099ede65aacc`

This document is a stage contract/evidence map only. The sole engineering-process authority remains
`docs/WORKING_PRINCIPLES.md`.

## Problem

The live roadmap requires regular long-horizon replay drills after changes in Python, providers,
models, storage and build infrastructure. LRD-01E already defines freshness-aware health, while
LRD-01K proves cross-environment replay evidence, but both dedicated workflows currently run only
on pull request, push or manual dispatch. A historical PASS therefore does not prove that later
revalidation happened on time, and a missed interval has no immutable first-class evidence.

LRD-01L closes only that orchestration/evidence gap. It does not schedule jobs, choose a business
cadence, or create a second replay/health authority.

## Existing authority reused

- LRD-01E remains the long-range health/freshness authority.
- LRD-01K remains the cross-environment replay/provenance authority.
- LRD-01D remains semantic-drift authority.
- LRD-01I and SSC-02 remain preserved-bundle and dependency/build-material authorities.
- Canonical Case Ledger remains the only writable Product case-history SSOT.

01L consumes verified upstream identities and states. It does not reinterpret semantic truth,
storage durability, cryptographic trust, Product facts, or release readiness.

## Cadence policy

`PeriodicReplayCadencePolicyV1` is immutable and content-addressed. It binds an explicit
`effective_at`, `max_replay_age_seconds`, and `due_window_seconds`, plus the fixed requirement that
LRD-01E health is `HEALTHY` and the upstream LRD-01K result remains semantically acceptable.

There is deliberately **no repository-wide default cadence in v1**. Supplying concrete policy
values is an operational input. The core never reads the wall clock and the dedicated workflow has
no `schedule:` trigger. This avoids silently turning an engineering mechanism into an unapproved
recurring external operation.

## Observation and chain

`PeriodicReplayObservationV1` binds one revalidation event to:

- exact full repository SHA as provenance;
- exact LRD-01I bundle identity carried by the verified LRD-01K report;
- exact content-addressed LRD-01K aggregate report;
- exact LRD-01E health report;
- caller-supplied observation time;
- derived upstream PASS/failure evidence;
- optional exact predecessor observation digest.

LRD-01K aggregate evidence is re-verified with its existing standalone verifier before observation
construction. An observation does not turn a failing, incompatible, unverifiable or semantic-drift
upstream result into PASS. `PRESENTATION_ONLY_DRIFT` remains acceptable because LRD-01D/01K already
classifies it as non-semantic drift; 01L does not redefine that classification.

Observation chains require one case scope, one exact LRD-01I bundle identity, strictly increasing
observation times, exact predecessor linkage and no duplicate observations. Reordering, gaps in
predecessor linkage, bundle substitution and content tampering fail closed.

## Evaluation states

`PeriodicReplayEvaluationV1` is immutable/content-addressed and exposes exactly:

- `CURRENT` — latest successful revalidation is outside the due window and no historical cadence
  gap exists under the supplied policy;
- `DUE` — latest successful revalidation is inside the due window but not overdue;
- `OVERDUE` — current age exceeds the bound, the initial deadline was missed, or a historical
  observation gap exceeded the policy bound;
- `UNVERIFIABLE` — required observation evidence is missing before its first deadline or the latest
  upstream revalidation itself is not a verified acceptable result.

A later successful run does not erase a historical missed interval under the same policy identity.
A deliberate operational reset therefore requires a new explicit cadence policy identity rather
than rewriting old evidence.

## Security and authority boundary

01L grants no scheduler, workflow-dispatch, Product, CCL, Gold, policy, trust-root, key custody,
storage, provider, merge, release or certification authority. Unknown fields/schemas/states,
invalid digests, invalid Git SHA, future timestamps, non-monotonic chains, duplicate/swapped
observations, upstream evidence substitution and scheduler-authority smuggling fail closed.

No provider is activated. The deferred provider-preservation backlog and its revisit date remain
unchanged. No AWS/provider PASS is claimed.

## Validation

Focused/adversarial coverage must include content addressing, strict schemas, CURRENT/DUE/OVERDUE/
UNVERIFIABLE boundaries, missing initial drill, historical missed interval, unhealthy LRD-01E
input, semantic drift from LRD-01K, evidence substitution, invalid SHA, future time, chain swap,
duplicate observation, digest tamper and scheduler-authority injection.

The dedicated exact-SHA workflow also re-runs LRD-01E, LRD-01K and LRD-01D regressions on supported
Python endpoints and explicitly rejects accidental introduction of a `schedule:` trigger.
Repo-wide security/policy/regression workflows remain mandatory before merge.

## Definition of Done

LRD-01L is closed only after one fresh exact candidate:

1. passes focused and adversarial tests without weakening upstream controls;
2. passes strict Ruff/MyPy and LRD-01D/01E/01K regressions;
3. passes the complete required exact-SHA repository CI set;
4. retains unchanged PR head/base before guarded merge;
5. is merged using the unchanged validated head;
6. completes terminal post-merge validation on resulting `main`;
7. leaves historical `v1.0.1` tag object, target and published release unchanged;
8. receives canonical closure evidence through a fresh closure SHA and resulting-main validation.

## Non-claims

Engineering PASS for 01L will not mean continuous monitoring is active. It will not prove that a
real recurring scheduler has run for any elapsed interval, choose an operational cadence, prove
10+ years of elapsed survivability, activate provider storage, perform disaster recovery, or claim
human/independent/security/regulatory certification.
