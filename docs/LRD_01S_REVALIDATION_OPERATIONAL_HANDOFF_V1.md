# LRD-01S — Revalidation Operational Handoff v1

Status: **CLOSED / ENGINEERING PASS**

## Problem

LRD-01R durably records which verified LRD-01Q lineage is operationally selected, but it intentionally does not compose a supplied candidate state into the next revalidation decision, fulfilment, baseline transition, immutable lineage extension, and durable selection.

LRD-01S closes only that measured local handoff gap. It composes the already-authoritative LRD-01M, LRD-01N, LRD-01P, LRD-01Q and LRD-01R contracts without introducing a repository watcher, scheduler, replay executor, mutable latest pointer, provider authority, or a second persistence subsystem.

## Handoff

One bounded handoff is:

`selected 01R lineage → current 01O baseline → 01M decision → 01N fulfilment → 01P transition → 01Q append → 01R compare-and-append selection`

The caller supplies:

- candidate LRD-01M fingerprint,
- candidate `RuntimeIdentity`,
- exact candidate repository SHA,
- optional already-produced replay report and exact replay repository SHA.

LRD-01S does not discover those inputs and does not execute replay.

## Fail-closed semantics

The handoff requires an existing verified 01R selection. It does not bootstrap an operational baseline implicitly.

The currently selected lineage supplies the exact prior verified baseline. LRD-01S then recomputes the downstream evidence chain using the existing contracts:

- unchanged candidate → `BASELINE_REUSED`, appended to the lineage and durably selected;
- changed candidate with no fresh replay evidence → `REVALIDATION_REQUIRED`, appended as a blocked lineage entry and durably selected without advancing the current verified baseline;
- changed candidate with acceptable exact replay evidence → `BASELINE_ADVANCED`, appended with the resulting verified baseline and durably selected;
- failed or unverifiable revalidation → blocked transition, no baseline advancement.

A repeated identical transition is rejected by existing LRD-01Q duplicate-transition semantics. Repository SHA, RuntimeIdentity, fingerprint, replay report and prior-selection substitutions remain fail-closed through the upstream contracts and the LRD-01R semantic ledger.

## Persistence and authority

LRD-01S creates no persistence system. The only durable write is delegated to the existing LRD-01R selection ledger and its existing `SQLiteProvenanceStore` compare-and-append path.

The current operational selection remains derived from the verified append-only selection stream tail. No mutable `latest` or `current` pointer is introduced.

Authority boundary:

- `selection_persistence_authority = true` only through the existing scoped LRD-01R append;
- `repository_change_detection_authority = false`;
- `scheduler_authority = false`;
- `replay_execution_authority = false`;
- `mutable_pointer_authority = false`;
- `release_authority = false`;
- `product_write_authority = false`;
- `ccl_write_authority = false`;
- `storage_authority = false`;
- `provider_authority = false`.

## Validation contract

LRD-01S validation covers:

- rejection when no selected baseline lineage exists;
- unchanged-candidate baseline reuse and durable strict extension;
- changed candidate without replay producing a durable blocked attempt without baseline advancement;
- changed candidate with verified replay advancing and durably selecting the new baseline;
- duplicate identical handoff rejection without an extra selection;
- candidate repository SHA substitution rejection before persistence;
- fingerprint/RuntimeIdentity substitution rejection before persistence;
- authority-boundary verification;
- full upstream 01R/01Q/01P/01O/01N/01M regression on Python 3.11 and 3.14.

## Explicit non-claims

LRD-01S does **not** provide:

- automatic Git/repository change detection,
- a filesystem or webhook watcher,
- scheduling or cron,
- replay execution or runner orchestration,
- automatic acquisition of fresh replay evidence,
- network or cloud/provider orchestration,
- provider durable storage authority,
- artifact storage authority,
- Product write authority,
- CCL write authority,
- release or tag mutation,
- policy or certification authority,
- a mutable latest/current pointer,
- a second persistence database.

Provider preservation remains deferred until **2027-03-09** unless requirements materially change.

## Canonical closure evidence

Implementation qualification:

- implementation PR: **#247**
- exact implementation candidate SHA: `50c2d177a9779e138eba9385e5465f0f481487eb`
- implementation PR base SHA: `ac6e43ad1b640a03f5f22908f541a3ea5198f4ba`
- exact-SHA pull-request workflow qualification: **41/41 SUCCESS**
- guarded implementation merge resulting main: `59999410c7fd5aac9728dc8dfb6e125c2144a776`
- resulting-main push validation: **37/37 SUCCESS**, 0 queued, 0 in-progress, 0 failure

Immutable release invariant after implementation merge:

- `v1.0.1` tag ref object SHA: `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
- annotated tag target commit: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- release name: `MVROS 1.0.1`
- release target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- invariant result: unchanged

This document is the canonical closure candidate. It may enter `main` only after exact-SHA closure CI and an unchanged head/base guarded merge. The final main push and release invariant are revalidated after that merge; no closure claim relies on an unobserved future result.
