# LRD-01S — Selected Baseline Revalidation Handoff v1

Status: **IMPLEMENTED / VALIDATION PENDING**

## Problem

LRD-01R closes the durable operational-selection gap by persisting which already-verified LRD-01Q lineage is selected. The remaining measured gap is composition: callers can invoke LRD-01M, 01N, 01P, 01Q and 01R independently, but they must themselves carry the correct selected baseline across those boundaries.

That leaves room for a caller to start revalidation from stale, unselected or substituted baseline evidence even though each individual stage is valid in isolation.

LRD-01S closes only that composition gap. It provides one caller-invoked, fail-closed handoff that always starts from the currently verified LRD-01R selection and either records the resulting blocked/reused transition or advances to exactly one new selected lineage extension.

## Existing authorities composed

LRD-01S does not redefine revalidation semantics. It composes the existing contracts in order:

1. **LRD-01R** — derive the currently selected and verified lineage.
2. **LRD-01M** — decide whether the candidate invalidates the selected baseline.
3. **LRD-01N** — bind that decision to exact replay fulfilment evidence.
4. **LRD-01P** — derive the exact baseline transition outcome.
5. **LRD-01Q** — append exactly one transition entry to the selected lineage.
6. **LRD-01R** — persist/select the strict lineage extension using existing transactional compare-and-append.

The prior baseline is never supplied independently by the caller. It is derived only from `current_selection().lineage.current_baseline` after LRD-01R verification.

## Bootstrap boundary

LRD-01S is not a bootstrap authority.

If the selection ledger has no current LRD-01R selection, the handoff fails closed without a write. The caller must perform an explicit LRD-01R bootstrap selection first.

This prevents an implicit or guessed genesis baseline from becoming operational authority through the convenience handoff.

## Outcomes

A single invocation produces exactly one LRD-01P transition and, if the compare-and-append succeeds, exactly one new LRD-01Q lineage entry plus one new LRD-01R selection.

The transition semantics remain those of LRD-01P:

- unchanged candidate evidence may produce `BASELINE_REUSED`,
- changed candidate evidence without valid replay fulfilment records a blocked `REVALIDATION_REQUIRED` attempt while preserving the current baseline,
- failed replay fulfilment records `REVALIDATION_FAILED` while preserving the current baseline,
- valid fulfilment may produce `BASELINE_ADVANCED` and advance the selected baseline.

Blocked attempts are operational history. They are appended and selected rather than silently discarded, so the selected lineage remains an auditable record of both successful and blocked revalidation attempts.

A byte-identical duplicate transition is rejected by the existing LRD-01Q duplicate-transition invariant and therefore cannot be replayed into the selected lineage as a second event.

## Race and stale-source safety

LRD-01S does not create a new lock or persistence layer.

The handoff reads the current verified LRD-01R selection, derives one strict lineage extension, and delegates persistence to the existing LRD-01R ledger. LRD-01R in turn delegates transactional compare-and-append to `SQLiteProvenanceStore` using the exact stream head.

If another writer selects a competing extension between the read and append, the stale writer fails closed. The handoff cannot overwrite or silently branch the selected lineage.

## Handoff receipt

The schema is:

`lukart.replay-revalidation-selected-handoff.v1`

The content-addressed receipt binds:

- the complete source LRD-01R selection,
- source selection digest,
- exact candidate fingerprint digest,
- exact candidate repository SHA,
- complete LRD-01M decision,
- complete LRD-01N fulfilment evidence,
- complete LRD-01P transition,
- transition state and derived baseline-change flag,
- complete persisted LRD-01R selection,
- persisted selection digest,
- explicit authority markers,
- deterministic handoff digest.

A pure verifier recomputes the 01M→01N→01P result from the supplied source/candidate/replay evidence, reconstructs the expected one-entry lineage extension and expected LRD-01R selection, and requires exact canonical equality with the receipt.

The receipt itself is not a new persistence stream. Persistence remains solely the existing LRD-01R selection stream in `SQLiteProvenanceStore`.

## Authority boundary

The handoff exposes only the already-approved narrow ability to persist the resulting LRD-01R selection:

- `selection_persistence_authority = true`
- `automatic_replay_authority = false`
- `scheduler_authority = false`
- `workflow_dispatch_authority = false`
- `mutable_pointer_authority = false`
- `release_authority = false`
- `product_write_authority = false`
- `ccl_write_authority = false`
- `storage_authority = false`
- `provider_authority = false`

The GitHub Actions workflow may expose the ordinary manual `workflow_dispatch` CI trigger. That is only a validation trigger and does not grant runtime workflow-dispatch authority to the LRD-01S core contract.

## Validation contract

LRD-01S validation covers at least:

- fail-closed behavior when no current selection exists,
- unchanged-candidate baseline reuse,
- changed-candidate blocked attempt without replay evidence,
- blocked attempt followed by valid replay and baseline advance,
- direct valid replay and baseline advance,
- semantic-drift replay failure with baseline preservation,
- candidate repository-SHA substitution rejection before selection write,
- stale-source race rejection through existing transactional compare-and-append,
- duplicate transition replay rejection,
- receipt canonical round-trip and pure recomputation,
- nested decision/fulfilment/transition tamper rejection,
- authority and unknown-field injection rejection,
- candidate/replay evidence substitution rejection,
- unrelated provenance-stream isolation,
- close/reopen recovery of the resulting selected lineage,
- upstream LRD-01R/01Q/01P/01N/01M regression.

The dedicated workflow uses read-only repository permissions, exact-candidate checkout, a frozen dependency environment, Python 3.11 and 3.14, Ruff, strict MyPy, focused/adversarial tests and upstream regression.

## Explicit non-claims

LRD-01S does **not** provide:

- repository-change discovery,
- replay execution or LRD-01K execution authority,
- automatic replay orchestration,
- a scheduler or cron authority,
- runtime workflow dispatch authority,
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
