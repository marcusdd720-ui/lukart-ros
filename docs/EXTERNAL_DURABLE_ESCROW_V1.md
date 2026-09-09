# LRD-01G — External Durable Escrow & Multi-Location Restore Conformance v1

Status: `CLOSED / ENGINEERING PASS` closure candidate; authoritative after guarded closure merge
Parent program: `continuous LRD-01`
Depends on: `LRD-01F CLOSED / ENGINEERING PASS`
Measured base: `main @ b48bfc87f2519ad085e3dacb3784a014e3098ff2`
Implementation PR: `#203`
Validated implementation head: `4448df1300abd04387f17dfa9b10d4bc5b5b32ab`
Implementation merge: `main @ 218aabda7495b79a0f98b29e0ba3fcff12842b21`
Implementation PR CI: `20/20 SUCCESS`
Implementation post-merge: `19/19 SUCCESS`, `queued=0`, `in_progress=0`, `failure=0`
Historical baseline tag object: `v1.0.1 @ 9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
Historical baseline target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
Latest release at implementation closure: `v1.0.1` / `MVROS 1.0.1`
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

LRD-01C proves exact physical artifact bytes, content-addressed storage portability and bounded
offline verification. LRD-01E proves a verified storage-portability drill and freshness-aware
long-range health. Neither control by itself proves that one exact LRD escrow can be replicated to
and independently restored from two declared locations whose storage profiles, failure domains and
credential domains are distinct.

A successful local filesystem copy is not ten-year durability evidence. Likewise, a caller-provided
provider name, location label or digest is not proof of WORM/object-lock, delete protection,
geographic separation, independent custody or retention enforcement. LRD-01G therefore separates
repository-verifiable engineering conformance from external durability evidence and fails closed
rather than manufacturing infrastructure claims.

## 2. Existing authority reused

LRD-01G composes existing contracts instead of creating a new storage or case-history authority:

- Canonical Case Ledger remains the sole writable Product case-history SSOT;
- LRD-01B remains the logical long-range replay artifact inventory and identity envelope;
- LRD-01C `ArtifactEscrowManifestV1`, `ArtifactEscrowBackendV1`, `EscrowBlobIdentityV1` and
  `migrate_verified_blob()` remain the exact physical-byte and verified migration boundary;
- DR-02 `StorageProfileV1` remains the content-addressed storage implementation/profile identity;
- LRD-01E remains the freshness/renewal/portability health authority.

No LRD-01G API writes CCL, Product state, Gold, policy, trust roots or release state.

## 3. Alternatives and decision

### A. Treat one filesystem escrow as durable multi-location storage

Rejected. A second directory on the same logical failure or credential domain is not independent
recovery evidence and cannot support a multi-location claim.

### B. Accept caller-declared cloud/WORM/geo capabilities as VERIFIED

Rejected. Self-attested metadata would convert an assertion into evidence and allow a false
external durability PASS without provider-side verification.

### C. Backend-neutral multi-location conformance over existing escrow — selected

The selected design binds two distinct DR-02 storage profiles plus distinct location, failure-domain
and credential-domain identities. Every preserved escrow blob is migrated only through the existing
verified read -> publish -> identity equality -> verified reread path, followed by independent
whole-location restore verification.

This closes the engineering semantics required before provider-specific durable adapters are added.

### D. Implement provider/object-lock adapters immediately

Deferred. A real external adapter requires provider credentials, provider API semantics, retention
configuration and independently observable evidence. Repository CI must not emulate those controls
and label them external durability.

## 4. Capability evidence model

Schema: `lukart.durability-capability-evidence.v1`.

Fixed v1 capability inventory:

- `EXACT_BYTE_VERIFICATION`;
- `IMMUTABLE_PUBLICATION`;
- `DELETE_PROTECTION`;
- `WORM_OBJECT_LOCK`;
- `GEOGRAPHIC_SEPARATION`;
- `INDEPENDENT_CREDENTIAL_DOMAIN`;
- `RETENTION_POLICY`.

The existing filesystem escrow can provide repository-verifiable engineering evidence for exact
byte verification and application-level immutable publication. Those two capabilities must be
`VERIFIED` with exact evidence identities.

Generic LRD-01G locations are structurally forbidden from marking delete protection, WORM/object
lock, geographic separation, independent credential-domain enforcement or retention policy as
`VERIFIED`. Those capabilities remain `UNVERIFIED` or `UNSUPPORTED` until a separately implemented
provider-specific verifier supplies evidence. A caller-supplied digest cannot promote them.

## 5. DurableEscrowLocationV1

Schema: `lukart.durable-escrow-location.v1`.

A location binds:

- exact DR-02 `StorageProfileV1` digest;
- canonical location ID;
- failure-domain ID;
- credential-domain ID;
- the fixed complete capability inventory;
- content-derived location identity.

A two-location plan fails closed if source and target share the same location identity, storage
profile, location ID, failure-domain ID or credential-domain ID. These declarations establish the
engineering conformance boundary; they do not certify physical geography or organizational custody.

## 6. Multi-location replication plan and receipt

Schemas:

- `lukart.multi-location-escrow-plan.v1`;
- `lukart.multi-location-replication-receipt.v1`.

The plan binds one exact case, exact LRD-01C escrow manifest, exact source/target location identities,
exact content-addressed blob-set identity, blob count and total bytes.

Replication calls the existing `migrate_verified_blob()` for every escrow binding. Therefore a
successful receipt requires:

1. verified source read by exact SHA-256 and size;
2. content-addressed target publication;
3. unchanged blob identity;
4. verified target reread;
5. exact aggregate count and byte total.

Location names, filenames and backend paths never substitute for artifact identity.

## 7. Independent restore conformance

Schema: `lukart.location-restore-report.v1`.

Each location is independently re-read against the exact escrow manifest. The report binds exact
case, escrow manifest, location, blob-set identity, expected/verified blob count, expected/verified
bytes and deterministic violations.

`PASS` requires every exact blob to be recoverable and verified. Missing or tampered material
produces explicit `FAIL`; partial success is never promoted.

The adversarial source-loss drill replicates the exact escrow to the second location, destroys the
source location, and then requires a complete target restore PASS. This tests source-independent
recoverability rather than merely comparing two live directories.

## 8. Aggregate conformance and external durability boundary

Schema: `lukart.multi-location-conformance-report.v1`.

The aggregate report binds the exact plan, replication receipt and both independent restore reports.
Engineering conformance is `PASS` only when both location restores pass.

External durability evidence is a separate state. Generic v1 locations cannot independently verify
provider-side WORM, delete protection, geographic separation, credential isolation or retention;
therefore repository-only LRD-01G evidence remains `INCOMPLETE` for external durability.

`ten_year_durability_claim` is structurally forced to `false`. Any serialized attempt to set it to
`true` fails closed. Engineering PASS is therefore not a ten-year SLA or archival certification.

## 9. Adversarial acceptance

The validated implementation proves:

- fixed complete capability inventory;
- engineering capabilities cannot be silently downgraded;
- generic locations cannot self-verify WORM or other external controls;
- source/target storage-profile collision rejection;
- failure-domain collision rejection;
- credential-domain collision rejection;
- exact all-blob verified replication;
- complete target restore after source destruction;
- one-byte target tampering produces FAIL;
- missing target object produces FAIL;
- cross-case substitution rejection;
- source/target location substitution rejection;
- unknown fields and content-digest tampering rejection;
- aggregate FAIL when either location fails restore;
- aggregate engineering PASS coexists only with explicit external evidence `INCOMPLETE`;
- ten-year durability claim fabrication is rejected;
- no CCL/Product write authority exists in the module.

LRD-01C path traversal, symlink, decompression-bomb and offline-runner tests remain regression
dependencies and were not weakened or duplicated.

## 10. Security and long-horizon boundaries

LRD-01G grants no:

- Canonical Case Ledger write authority;
- Product/Gold/policy/trust mutation authority;
- provider credential storage authority;
- release/tag authority;
- generic cloud/backend certification;
- WORM/object-lock or geographic-separation claim without provider-specific evidence;
- ten-year durability SLA;
- independent security, archival, regulatory or cryptographic certification.

Location/failure/credential-domain declarations are content-addressed provenance inputs. A future
external adapter must verify the semantics it claims rather than inheriting generic v1 PASS.

## 11. Implementation closure evidence

The implementation was developed from exact measured base
`b48bfc87f2519ad085e3dacb3784a014e3098ff2` in PR #203. The final implementation head
`4448df1300abd04387f17dfa9b10d4bc5b5b32ab` passed all 20 PR-triggered workflows on one unchanged
exact SHA. The set included the dedicated `LRD-01G External Durable Escrow Conformance`, CI
Foundation, Stage Gate, Enterprise CodeQL, Enterprise Hardcore Gate, LRD-01C, LRD-01D, LRD-01E,
LRD-01F, SSC-02, FIV-02, OPR-01 and Production Validation Program.

The dedicated LRD-01G workflow verified exact checkout, Ruff, strict MyPy, focused/adversarial tests,
LRD escrow/recovery/health/drift/PQC regression and a fail-closed adversarial selection. No test,
threshold, trust boundary or security gate was weakened to obtain PASS.

Before merge, live GitHub still reported PR #203 head
`4448df1300abd04387f17dfa9b10d4bc5b5b32ab`, base `main`, and base SHA
`b48bfc87f2519ad085e3dacb3784a014e3098ff2`. Guarded merge used the exact expected head and
produced implementation main `218aabda7495b79a0f98b29e0ba3fcff12842b21`. Its direct parents are the
measured base and the validated implementation head.

The exact implementation main completed 19 recorded post-merge workflow runs, all terminal
`SUCCESS`, with zero failed, queued or in-progress runs at implementation closure evaluation. The
set included the dedicated LRD-01G workflow, Stage Gate, Enterprise CodeQL, Enterprise Hardcore,
Production Validation, governance closure preparation and the `MVROS v1 Release` guard.

Governance closure preparation completed successfully but did not produce an LRD-01G closure PR;
therefore canonical closure is recorded through this controller-side closure candidate rather than
manufacturing automation support for an unconfigured stage selector.

Historical release identity remained unchanged after implementation merge. The `v1.0.1` annotated
tag object remained `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`, that tag still targets
`802013c4d0e53dc12306a97e1877ebba86af64a7`, and the latest published release remains `v1.0.1` /
`MVROS 1.0.1`. No release/tag publication or movement is authorized by LRD-01G.

This record becomes authoritative only after this exact closure candidate itself passes fresh
exact-head CI, guarded closure merge, resulting-main validation and final baseline/release
re-verification. Implementation PASS does not become external durability evidence: provider-side
WORM/delete-protection/geography/retention/custody evidence remains `INCOMPLETE` by design.

## 12. Definition of Done

LRD-01G closes only after one exact closure line proves:

1. strict capability/location/plan/receipt/restore/conformance contracts;
2. exact two-location profile/failure-domain/credential-domain separation;
3. all-artifact replication through LRD-01C verified migration primitives;
4. independent full restore from each location;
5. target restore after destructive source loss;
6. explicit separation of engineering conformance from external durability evidence;
7. structural prohibition of fabricated ten-year durability claims;
8. focused and adversarial tests;
9. LRD-01C, DR-02, LRD-01D, LRD-01E and LRD-01F regression;
10. Ruff, strict MyPy, full repository regression and security/policy gates;
11. implementation exact-head `20/20 SUCCESS`;
12. guarded implementation merge and implementation-main `19/19 SUCCESS`;
13. historical `v1.0.1` tag/target/release baseline unchanged after implementation;
14. fresh exact-head CI for this closure candidate;
15. guarded closure merge;
16. resulting final-main post-merge validation terminal `SUCCESS`;
17. final historical `v1.0.1` tag/target/release re-verification.

## 13. Next boundary

No later LRD slice is authorized by this document. Provider-specific external durable-storage
verification, hermetic runtime preservation/stronger isolation, generic external execution capture
or a post-quantum signing adapter each require separate evidence and separately approved scope.
