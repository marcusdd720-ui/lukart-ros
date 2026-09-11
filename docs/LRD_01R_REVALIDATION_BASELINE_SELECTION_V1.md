# LRD-01R — Revalidation Baseline Selection Ledger v1

Status: **CLOSED / ENGINEERING PASS**

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

## Canonical closure evidence

Implementation qualification:

- implementation PR: **#244**
- exact implementation candidate SHA: `c23b30f4aa9b87ab740416933f181a9ec00cc04b`
- implementation PR base SHA: `c21f3c4577c17c012b7101becb2f9e7c32949778`
- PR head/base guard: unchanged immediately before merge
- PR mergeability: `true`
- dedicated LRD-01R gate: Python 3.11 and 3.14 both passed exact checkout, frozen environment, Ruff, strict MyPy, focused suite, adversarial suite, full 01R suite, upstream replay-revalidation regression and authority-boundary verification
- full exact-SHA PR workflow set: all observed workflows completed successfully with no failure before guarded merge
- guarded implementation merge resulting main: `4f52be9a92a2043216d84e4484da03b34f8d7c4e`
- resulting-main push validation: **36/36 SUCCESS**, 0 queued, 0 in-progress, 0 failure

Immutable release invariant after implementation merge:

- `v1.0.1` tag ref object SHA: `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
- annotated tag target commit: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- release name: `MVROS 1.0.1`
- release target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
- invariant result: unchanged

This document is the canonical closure candidate. It may enter `main` only after exact-SHA closure CI and an unchanged head/base guarded merge. The final main push and release invariant are revalidated after that merge; no closure claim relies on an unobserved future result.
