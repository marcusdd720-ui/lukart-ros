# LUKART ROS — Post-Hardcore Enterprise Roadmap

Status: Active continuation after historical H1-H10 ENGINEERING PASS
Program baseline: `main @ eefd7088406126c0a20baf1245742649058decc4`
Horizon: 10+ years

This roadmap extends the existing Product, P2/P3, Enterprise and historical Hardcore
controls. It MUST NOT create a parallel Product truth authority, silently reinterpret
historical evidence, weaken exact-SHA validation or manufacture independent review.

## Architectural invariant

The Canonical Case Ledger is the only authoritative writable SSOT for case history.
Everything downstream is an immutable input or a deterministic/versioned projection.

Canonical trust chain:

`Evidence -> Canonical Ledger -> Epistemic State -> Trust Graph -> Reasoning -> Result`
`-> Change Invalidation -> Recompute -> Replay -> independently verifiable evidence`

Cross-cutting requirements:

- fail closed;
- least privilege;
- exact/content-addressed identity;
- explicit canonicalization and digest identifiers;
- tamper-evident storage and case history;
- offline-verifiable evidence;
- immutable once published;
- deterministic replay;
- explicit versioned migrations;
- unknown migration/schema/profile/algorithm -> FAIL;
- bounded propagation and blast radius;
- adversarial/negative testing;
- provider/model/storage independence;
- exact-SHA validation and guarded merge;
- future-resistant, not future-predictive;
- Best-Justified Solution != Most Complex Solution.

## PHX-01 — Canonical Case Ledger / Object Identity Contract v1

Goal: establish one logical case-history authority before additional cognitive layers are
strengthened.

Required controls:

- stable logical Case/Object identity separated from immutable revision/event identity;
- content-addressed revisions and events;
- canonical event chain per case;
- exact caller head plus transactional backend compare-and-append;
- reuse existing Enterprise durable backend instead of adding a third store;
- existing P3 JSONL replay ledger explicitly non-authoritative for Product truth;
- schema/canonicalization/hash identifiers are explicit and unknown values fail closed;
- offline content-addressed case bundle;
- bounded case reads/exports;
- strict type boundary and adversarial tests.

Architecture contract: `docs/CANONICAL_CASE_LEDGER_V1.md`.

## PHX-02 — Gold Corpus / KQM v2

Goal: make evaluation inputs immutable, content-addressed and ledger-bound without
turning evaluation data into case truth.

Controls:

- Gold corpus manifests and splits are immutable/versioned inputs;
- locked evaluation cannot be tuned against;
- exact corpus, metric definition and evaluator identity are recorded;
- KQM outputs are projections/measurements, never truth promotion;
- corpus mutation produces a new identity and invalidates dependent measurements;
- independent freeze/review evidence remains explicit rather than self-certified.

Indicative horizon: year 1-2.

## PHX-03 — Epistemic Assertion + State Machine v2

Goal: convert epistemic state from mutable object fields into deterministic ledger-derived
state over immutable assertions and transition events.

Controls:

- first-class immutable Assertion identity;
- exact evidence references for FACT promotion;
- transition policy version and decision identity;
- UNKNOWN, UNRESOLVED, REJECTED and abstention remain first-class;
- no model/provider/plugin can silently promote trusted state;
- state can be rebuilt from ledger history.

Indicative horizon: year 2-3.

## PHX-04 — Evidence Trust Graph

Goal: provide a deterministic trust projection over exact evidence/assertion identities.

Controls:

- typed evidence/assertion/trust edges;
- provenance, authorization and contradiction edges;
- explicit trust-policy version;
- cryptographic attestation is evidence, not automatic epistemic truth;
- graph rebuild from ledger and policy identity;
- no writable graph authority separate from ledger.

Indicative horizon: year 3-4.

## PHX-05 — Case Replay v2

Goal: independently reproduce a case result from exact identities and explicit migrations.

Controls:

- replay manifest binds ledger head, schemas, migration registry, projection versions,
  runtime identity, provider/model/plugin/config/corpus identities and evidence blobs;
- IDENTICAL requires complete exact identity;
- cross-version comparison requires explicit deterministic migration;
- unknown/ambiguous migration fails closed;
- replay bundle is verifiable offline.

Indicative horizon: year 4-5.

## PHX-06 — Semantic Change Propagation v2

Goal: invalidate and recompute exactly the affected projections when immutable input
identity changes.

Controls:

- dependency edges point to exact immutable revision/event IDs;
- deterministic affected set;
- explicit node/depth/work budgets;
- exceeding budget returns a hard explicit state such as `BLAST_RADIUS_EXCEEDED`;
- no silent truncation;
- recomputed outputs receive new identities and lineage;
- replay proves propagation result.

Indicative horizon: year 5-6.

## Years 6-10+ — Durability, portability and cryptographic renewal

### Storage portability / disaster recovery

The Canonical Ledger remains a contract, not a database brand. SQLite is the default
reference backend until measured requirements justify another implementation. Any new
backend must pass the same canonical identity/conformance suite and preserve exact event
bytes/identity. Recovery drills must prove state identity after backup/restore.

### Signed case exchange

Introduce portable evidence bundles containing ledger slices/checkpoints, schemas,
migrations, policies, immutable inputs and verification material. Cross-case/tenant
references require explicit authorization and cannot merge epistemic authorities by
implication.

### Critical-invariant verification

Apply property/state-machine/model checking to small trust-critical contracts such as
append-only history, identity uniqueness, deterministic migration, authorization,
projection rebuild equivalence, concurrent-head rejection and crash recovery. Do not
attempt speculative formal verification of the whole product.

### Cryptographic renewal

Digest/signature algorithms and canonicalization profiles remain versioned identifiers.
Future changes create explicit new identities/migrations while historical bundles remain
offline-verifiable. Regular long-horizon replay drills must demonstrate that historical
cases remain verifiable after changes in Python, providers, models, storage and build
infrastructure.

## Closure semantics

A roadmap stage is not DONE because code exists, a PR exists, CI is partially green or a
document says so. Closure requires exact candidate identity, focused/adversarial/full
validation, complete required CI, guarded exact-head merge and post-merge verification.
External independent review remains separately evidenced where required.
