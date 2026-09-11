# LRD-01S — Revalidation Operational Handoff v1

Status: **IMPLEMENTED / VALIDATION PENDING**

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

## Closure evidence

Canonical implementation SHA, exact-SHA CI evidence, PR/merge identity, resulting `main`, post-merge validation and immutable `v1.0.1` verification will be recorded only after those facts are observed. Until then this stage remains **IMPLEMENTED / VALIDATION PENDING**.
