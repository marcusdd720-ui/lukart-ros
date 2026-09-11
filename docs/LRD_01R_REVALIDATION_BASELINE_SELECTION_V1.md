# LRD-01R — Revalidation Baseline Selection Ledger v1

Status: **IMPLEMENTED / VALIDATION PENDING**

## Problem

LRD-01Q establishes a self-contained, canonical and append-only lineage of replay-revalidation baseline transitions and deterministically derives the current verified baseline from that lineage. It intentionally does not persist or operationally select which verified lineage is authoritative.

LRD-01R closes only that measured gap. It records which already-verified LRD-01Q lineage is operationally selected without introducing a mutable `latest` pointer, a second persistence subsystem, a scheduler, provider authority, or Product/CCL write authority.

## Design

LRD-01R reuses the existing `SQLiteProvenanceStore` as the sole durable persistence primitive. The implementation does not create a competing database or storage abstraction.

Selections are written to the dedicated append-only stream:

`system:lrd-revalidation-baseline-selection:v1`

with event type:

`lrd.revalidation-baseline-selection.v1`

Every selection record embeds the full canonical LRD-01Q lineage snapshot and binds:

- the exact lineage digest,
- the derived current baseline digest,
- the derived current repository SHA,
- the previous semantic selection digest,
- a deterministic content-addressed selection digest,
- explicit scoped authority markers.

The operationally current selection is derived from the final verified selection record in the dedicated stream. There is no independently mutable current/latest pointer.

## Strict extension rule

After the first valid selection, every later selected lineage must be a strict extension of the previously selected lineage:

- the genesis baseline must be identical,
- every prior lineage entry must remain an exact prefix,
- at least one new lineage entry must be added,
- selecting the identical lineage is rejected as a no-op,
- selecting a shorter lineage is rejected as rollback,
- selecting a non-prefix lineage is rejected as fork/reorder.

A blocked-only extension is a valid new selection even when the current verified baseline remains unchanged. A successful revalidation extension may advance the current verified baseline.

## Persistence and concurrency semantics

`SQLiteProvenanceStore` already exposes a per-stream content-addressed head. An empty stream has a canonical genesis head. LRD-01R reads that exact stream head and supplies it to `append(..., expected_stream_head=...)`.

The existing persistence layer checks the expected head inside the same SQLite `BEGIN IMMEDIATE` transaction that performs the append. Therefore the first write and every later write use the same fail-closed compare-and-append mechanism; LRD-01R does not add a parallel lock or persistence authority.

Before deriving selection state, LRD-01R verifies the lower-level durable provenance chain. It then independently verifies the selection event type, canonical payload, semantic selection-digest chain, full LRD-01Q lineage, lineage-extension invariant and authority markers. A payload can therefore be internally valid at the SQLite provenance hash-chain layer and still be rejected by the LRD-01R semantic verifier.

## Authority boundary

The only authority introduced by this stage is the narrow ability to persist an LRD-01R selection event in the existing provenance store:

- `selection_persistence_authority = true`
- `mutable_pointer_authority = false`
- `scheduler_authority = false`
- `release_authority = false`
- `product_write_authority = false`
- `ccl_write_authority = false`
- `storage_authority = false`
- `provider_authority = false`

This is not a grant of broad persistence authority and is not an artifact escrow/storage authority.

## Validation contract

LRD-01R validation covers:

- first selection persistence,
- close/reopen recovery of the same current selection,
- strict blocked-only lineage extension,
- successful baseline-advancing extension,
- duplicate/no-op rejection,
- rollback rejection,
- fork/reorder rejection,
- semantic previous-selection-digest tamper rejection,
- summary and selection-digest tamper rejection,
- unknown event type rejection in the dedicated stream,
- isolation from unrelated provenance streams,
- authority/unknown-field injection rejection,
- semantic rejection even when lower-level durable integrity remains valid,
- stale genesis stream-head race rejection using the existing transactional compare-and-append primitive,
- upstream LRD-01Q/01P/01O revalidation regression.

## Explicit non-claims

LRD-01R does **not** provide:

- scheduling or cron authority,
- automatic repository-change detection,
- an operational replay/revalidation orchestration loop,
- cloud/provider durable storage,
- artifact storage authority,
- Product write authority,
- CCL write authority,
- release or tag mutation,
- a mutable latest/current pointer,
- a new general-purpose persistence authority,
- certification authority.

Provider preservation remains deferred until **2027-03-09** unless requirements materially change.

## Closure evidence

Canonical implementation SHA, exact-SHA CI evidence, PR/merge identity, resulting `main`, post-merge validation and immutable `v1.0.1` verification will be recorded only after those facts are observed. Until then this stage remains **IMPLEMENTED / VALIDATION PENDING**.
