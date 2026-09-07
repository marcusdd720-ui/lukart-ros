# Canonical Case Ledger / Object Identity Contract v1

Status: Active Post-Hardcore architecture contract
Baseline at program start: `main @ eefd7088406126c0a20baf1245742649058decc4`
Authority: Product case-history SSOT

## 1. Decision

The Canonical Case Ledger is the only authoritative writable source of case history.
Gold Corpus, epistemic state, trust graphs, timelines, reasoning outputs, renderer
artifacts, search indexes and later semantic-change machinery MUST be immutable inputs
or deterministic/versioned projections over canonical ledger history. They MUST NOT
become competing sources of truth.

Trust chain:

`Evidence -> Canonical Ledger -> Epistemic State -> Trust Graph -> Reasoning -> Result`
`-> Change Invalidation -> Recompute -> Replay -> independently verifiable evidence`

## 2. Best-justified architecture

CCL v1 does not introduce a third database, blockchain, distributed consensus system,
CRDT or message broker. The existing `SQLiteProvenanceStore` is reused as the durable,
transactional backend. Canonical event identity is intentionally independent of SQLite
record identity so the same canonical bytes can later be verified after a storage
backend replacement.

The existing P3 JSONL `AppendOnlyReplayLedger` remains a historical replay/provenance
mechanism and possible migration input. It is not a Product truth authority. The
Enterprise SQLite provenance store is durability infrastructure, not an epistemic or
case-history authority. New authoritative case writes go through `CanonicalCaseLedger`.

This preserves the rule: **one logical authority, replaceable storage implementations**.

## 3. Identity model

CCL separates two identity classes:

1. Logical identity — stable `CaseId` and `ObjectId`. These identify the continuing
   logical entity and are not silently normalized. Leading/trailing whitespace or
   control characters fail closed.
2. Immutable content identity — `ObjectRevision.revision_id`, `LedgerEvent.event_id`
   and bundle identity. These are content-addressed and include their exact semantic
   inputs.

Changing object content changes its revision identity. Changing object identity changes
revision identity even if content is byte-for-byte equivalent. A published revision is
never edited in place; a later correction is represented by a later event/revision.

## 4. Canonicalization and cryptographic agility

CCL v1 explicitly records:

- event/revision schema identity;
- canonicalization profile identity: `lukart.canonical-json.v1`;
- digest algorithm identity: `sha256`.

The v1 profile reuses the existing P3 deterministic canonical JSON contract. Unknown
schema, canonicalization profile or digest algorithm is a hard FAIL. A future profile or
algorithm therefore requires an explicit versioned reader/migration change; it cannot be
silently interpreted as v1.

SHA-256 is the current algorithm, not a permanent assumption of the data model. The
content-address envelope contains the algorithm identifier so future cryptographic
renewal does not require redefining logical object identity.

## 5. Event model

Every canonical event binds at least:

- exact `case_id`;
- per-case monotonic `case_sequence`;
- versioned `event_type`;
- exact prior canonical event identity, except genesis;
- runtime identity digest;
- canonical payload;
- optional logical `object_id` and immutable `revision_id`;
- canonicalization profile and event schema;
- content-addressed event identity.

The event ID is calculated over the complete canonical event body. Event ordering and
previous-head identity therefore participate in the content address: replaying the same
payload onto a different history does not manufacture an identical event.

## 6. Atomic expected-head writes

A write is accepted only when the caller's canonical `expected_head` matches the current
case head. CCL also binds the same append to the exact durable backend stream head by a
compare-and-append check inside `BEGIN IMMEDIATE`.

This prevents lost updates across separate processes:

1. read and verify canonical/backend snapshot;
2. compare caller canonical head;
3. build the next immutable canonical event;
4. transactionally compare backend stream head;
5. append or rollback;
6. re-read and verify exact resulting event.

A concurrent/stale head is a FAIL, never last-writer-wins.

## 7. Tamper evidence and offline verification

CCL has independent verification layers:

- backend SQLite global hash chain;
- per-case canonical event hash chain;
- content address of every event/revision;
- content-addressed `CaseLedgerBundle` for offline verification.

An exported bundle contains all canonical events for one bounded case view and can be
verified without access to the database. A modified payload, sequence, previous event,
revision address, event ID or bundle digest fails verification.

Signing/attestation of bundles is a later transport/release boundary. Cryptographic
signatures must not replace content verification.

## 8. Immutability and least privilege

`CanonicalCaseLedger` intentionally exposes append, read, head and export/verify
operations. It exposes no edit/delete/rewrite API. Corrections, retractions,
supersession and future epistemic transitions are new events.

The durable backend retains backup/recovery responsibilities but does not gain Product
reasoning or epistemic promotion authority.

## 9. Bounded behavior

Case reads, exports and writes have an explicit maximum-event bound. Exceeding the
configured bound fails closed rather than truncating history. Future pagination/scale
work may change transport mechanics but must preserve exact full-history identity and
make partial views explicit.

Semantic propagation limits are intentionally deferred to Semantic Change Propagation
v2; CCL only establishes exact dependency identities needed by that later stage.

## 10. Migration policy

CCL v1 accepts only v1 revision/event/bundle schemas. There is no implicit migration.
Unknown schema means FAIL.

When v2 is justified, migration must be:

- explicit and versioned;
- deterministic;
- non-mutating to the source history;
- identity-producing rather than identity-rewriting;
- independently replayable;
- covered by adversarial tests for missing, ambiguous and non-deterministic migration.

Existing P3 `CaseMigrationRegistry` remains the established migration-pattern authority;
future CCL migration work must extend or adapt that pattern rather than create an
unrelated silent migration mechanism.

## 11. Projection rule

Downstream components may store caches/materialized views only when all of the following
are true:

- projection version is explicit;
- exact input ledger head is recorded;
- output is deterministically rebuildable or explicitly marked non-deterministic and
  non-authoritative;
- invalidation is triggered when an input revision/event changes;
- missing/unknown dependency identity becomes `UNKNOWN`/`UNRESOLVED` or FAIL, never PASS;
- projection data cannot overwrite canonical ledger history.

## 12. Required acceptance evidence

CCL v1 cannot be considered engineering-complete without:

- deterministic identity tests;
- unknown-schema/profile/algorithm negative tests;
- stale-head atomicity test;
- independent case-stream sequence test;
- rogue/parallel-authority record rejection;
- tampered event and offline bundle rejection;
- explicit blast-radius limit test;
- provider identity independence test;
- strict trust-boundary MyPy coverage;
- Ruff, MyPy, focused tests, adversarial tests and full regression;
- complete required CI on one exact candidate SHA;
- guarded exact-SHA merge and post-merge validation.

Green CI is engineering evidence only. It is not independent external certification.
