# LUKART ROS — Post-Hardcore Enterprise Roadmap

Status: Active continuation after historical H1-H10 ENGINEERING PASS
Program baseline: `main @ eefd7088406126c0a20baf1245742649058decc4`
Current closed trust core: `PHX-06 @ main 9c2a7812cedfe98b65af484186459300897357de`
Latest closed durability continuation: `DR-01 implementation merge @ main 615c01946e7ca61bb0bb5488b2a3b799eb5f06ce`
Active stage: `NONE — PHX-01..PHX-06 trust core and DR-01 closed`
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

Status: `CLOSED / ENGINEERING PASS`
Merge baseline: `main @ 796bbce41ecfa5bc8bdabea70a4d31d6b4ff2cfd`

Closed controls:

- stable logical Case/Object identity separated from immutable revision/event identity;
- content-addressed revisions and events;
- canonical event chain per case;
- exact caller head plus transactional backend compare-and-append;
- Enterprise durable backend reused instead of adding a third store;
- schema/canonicalization/hash identifiers explicit and unknown values fail closed;
- offline content-addressed case bundle;
- bounded case reads/exports;
- exact-SHA guarded merge and post-merge workflow closure.

Architecture contract: `docs/CANONICAL_CASE_LEDGER_V1.md`.

## PHX-02 — Gold Corpus / KQM v2

Status: `CLOSED / ENGINEERING PASS`
Merge baseline: `main @ a0fa7e128366bc26419ae820d3ce88691a55723a`
Validated PR head: `0521a798a87eae98828c2a052c2e3e2aea2040ce`
PR: `#151`

Closed controls:

- distinct raw-file and canonical semantic Gold identities;
- immutable/versioned manifest and exact split membership;
- locked evaluation inaccessible to development/validation;
- independent freeze/review cannot be manufactured by repository code/text;
- exact corpus, policy, evaluator/runtime and per-case CCL heads bound into evaluation identity;
- KQM policy versioned/content-addressed with strict typed controls;
- missing metric FAIL, unexpected/non-finite metric contract rejection;
- KQM outputs immutable measurement projections, never truth promotion;
- no Canonical Ledger write path from PHX-02;
- canonical governance SSOT hardened: `docs/WORKING_PRINCIPLES.md` <=8000 characters,
  thin `AGENTS.md`, authority alignment and executable duplicate/limit guards;
- exact-SHA CI and post-merge validation closed with historical `v1.0.1` unchanged.

Architecture contract: `docs/GOLD_KQM_V2.md`.

## PHX-03 — Epistemic Assertion + State Machine v2

Status: `CLOSED / ENGINEERING PASS`
Merge baseline: `main @ d01f2d6e87a900d77ee25f95fe273a855d85cf32`
Validated PR head: `e63e0898d7f50b9738ba7dddb83bfc719b28fa82`
PR: `#152`

Closed controls:

- first-class immutable/content-addressed Assertion identity;
- exact `case_id + CCL event_id` evidence references;
- FACT creation/promotion requires prior policy-authorized evidence events;
- transition policy identity binds transition machine and evidence-event policy;
- transition decisions are content-addressed and replay-verified;
- denied/no-op/unknown transitions never become authoritative state;
- cross-case evidence fails closed until a separately versioned trust contract exists;
- `CaseScope.epistemic_state` is legacy/non-authoritative and cannot be changed by
  `with_states()`;
- state is a deterministic projection over exact CCL history and ledger head;
- no epistemic persistence authority exists outside Canonical Case Ledger;
- exact-SHA CI, guarded merge and post-merge validation closed.

Architecture contract: `docs/EPISTEMIC_ASSERTIONS_V2.md`.

## PHX-04 — Evidence Trust Graph

Status: `CLOSED / ENGINEERING PASS`
Merge baseline: `main @ b26bc4128651367efb636d7e4d53d0b1e79cffeb`
Validated PR head: `2aeb2d144944a99a47417fbc24233198fb7e083a`
PR: `#153`

Closed controls:

- typed EVENT / ASSERTION / DECISION nodes bound to exact content identities;
- exact SUPPORTS / TRANSITIONS / RECORDED_BY provenance edges;
- CONTRADICTS / AUTHORIZED_BY / ATTESTED_BY only from explicit canonical relation events;
- explicit content-addressed trust-policy identity and hard node/edge budgets;
- cryptographic attestation represents origin/integrity evidence, never epistemic truth;
- cross-case/dangling references and unknown `trust.*` events fail closed;
- graph identity binds exact case ledger head, Epistemic projection identity and policy;
- no graph DB, graph write API or Canonical Ledger write path exists in the projection;
- exact-SHA CI, guarded merge and post-merge validation closed.

Architecture contract: `docs/EVIDENCE_TRUST_GRAPH_V1.md`.

## PHX-05 — Case Replay v2

Status: `CLOSED / ENGINEERING PASS`
Merge baseline: `main @ e8266b8dc0c76c297d63465df63b166cacb83b0a`
Validated PR head: `d49173e510e38c60890e91f1cbb4bae726625af8`
PR: `#154`

Closed controls:

- replay manifest binds exact case, CCL head and content-addressed ledger bundle;
- manifest binds Epistemic v2 and Trust Graph projection/policy identities;
- RuntimeIdentity v3 binds code/config/corpus/provider/plugin/input/evidence and execution
  environment declarations;
- complete replay schema identities and deterministic migration-registry identity are
  explicit and content-addressed;
- offline bundle rebuilds Epistemic v2 and Trust Graph without live database/provider
  access and verifies rebuilt identities against the manifest;
- `IDENTICAL` requires complete exact manifest identity;
- cross-version comparison requires an explicit deterministic migration path;
- unknown fields/schemas, ambiguous migration, incomplete runtime, cross-case substitution
  or tampering fail closed;
- replay is verification-only and exposes no Canonical Ledger write path;
- exact-SHA CI, guarded merge and terminal post-merge validation closed.

Architecture contract: `docs/CASE_REPLAY_V2.md`.

## PHX-06 — Semantic Change Propagation v2

Status: `CLOSED / ENGINEERING PASS`
Merge baseline: `main @ 9c2a7812cedfe98b65af484186459300897357de`
Validated PR head: `05b7046404078bd79e2d15ebfb2af1dc8968b16f`
PR: `#155`

Closed controls:

- typed case-scoped dependency refs point only to exact immutable content identities;
- existing P3 graph cycle/self-reference semantics are reused without breaking legacy API;
- deterministic affected set and optional deterministic materialized paths;
- content-addressed propagation-policy identity;
- explicit node/depth/work budgets;
- exceeding a budget raises hard `BLAST_RADIUS_EXCEEDED` with NODES/DEPTH/WORK reason;
- no silent truncation or partial PASS;
- propagation plan binds exact graph, policy and Case Replay v2 manifest identities;
- stale/wrong replay identity fails closed;
- recomputed outputs receive new lineage-bound result identity while historical results
  remain immutable;
- cross-case dependencies fail closed;
- no graph DB, persistence authority or CCL write path is introduced;
- exact-SHA CI passed 11/11 required PR workflows before guarded exact-head merge;
- terminal post-merge validation on the implementation merge had no queued/in-progress,
  failed or cancelled workflow runs.

Architecture contract: `docs/SEMANTIC_CHANGE_PROPAGATION_V2.md`.

## DR-01 — Canonical Ledger Recovery / Storage Portability v1

Status: `CLOSED / ENGINEERING PASS`
Implementation merge baseline: `main @ 615c01946e7ca61bb0bb5488b2a3b799eb5f06ce`
Validated PR head: `15312711bed0956d614de6fc3ee5005cc96f55dd`
PR: `#157`
Post-merge Stage Gate: run ID `34155_634951` — `SUCCESS` (underscore is a display separator for the repository PII gate)

Closed controls:

- existing `CaseLedgerBundle` is reused as the storage-portable case artifact; no parallel
  backup format or second Product SSOT is introduced;
- source bundle is fully fail-closed verified before any restore write, including rejection
  of unbound/inconsistent serialized metadata and unknown extra fields;
- restore requires an explicit matching target `CaseId`;
- restore into an existing non-empty target case stream fails instead of merging,
  overwriting or silently forking authoritative history;
- existing Enterprise `SQLiteProvenanceStore.append_batch` is reused as the atomic
  transactional durability primitive;
- exact target backend stream head is checked in the same transaction used for restore;
- injected failure on the second event proves full rollback with zero partial case history;
- restored canonical event IDs, case head and bundle digest are exactly identical to the
  source bundle even when unrelated target-backend records change backend-global position;
- backend durability record identities may be regenerated because they are infrastructure
  provenance, not Product epistemic identity;
- bounded restore size fails before write;
- empty bundle restore is a verified no-op;
- exact candidate SHA passed all 11 required PR workflows before guarded exact-head merge;
- exact implementation merge SHA completed nine post-merge workflows with no queued,
  in-progress, failed, cancelled or timed-out runs; all nine concluded `SUCCESS`;
- historical `v1.0.1` identity remains unchanged;
- engineering closure does not claim independent external certification.

DR-01 is the first implemented control under the long-horizon storage portability /
disaster-recovery continuation. No subsequent DR stage is active until separately defined,
measured and validated.

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
