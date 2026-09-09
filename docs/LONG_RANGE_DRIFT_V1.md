# LRD-01D — Frozen Path / Current Path / Drift Evidence v1

Status: `CLOSED / ENGINEERING PASS` closure candidate; authoritative after guarded closure merge
Parent program: `continuous LRD-01`
Depends on: `LRD-01C CLOSED / ENGINEERING PASS`
Measured base: `main @ f601e9eae598c8c40eb365f343a100717c10bfb4`
Implementation PR: `#197`
Validated implementation head: `6052fcb55af4dfb6cf2cd2fed76d22e8d9b0a3f6`
Implementation merge: `main @ 57356225a41479274d6be00044e6c861f268a0b1`
Implementation PR CI: `17/17 SUCCESS`
Implementation post-merge: `16/16 SUCCESS`, `queued=0`, `in_progress=0`, `failure=0`
Historical baseline tag object: `v1.0.1 @ 9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
Historical baseline target: `802013c4d0e53dc12306a97e1877ebba86af64a7`
Latest release at implementation closure: `v1.0.1`
Writable case-history SSOT: Canonical Case Ledger only

## 1. Problem

LRD-01B binds exact long-range replay identity and separates canonical semantic identity from
presentation identity. LRD-01C proves that `PRESERVED` artifacts have verified bytes and can be
read under a least-privilege process boundary with declared network `OFF`. Neither stage by itself
proves that historical deterministic replay state can be reconstructed from those bytes or that a
new execution through the current supported Product stack can be compared without rewriting
history.

LRD-01D closes that boundary. It must distinguish three different questions:

1. Can the historical deterministic replay state be rebuilt from exact preserved bytes?
2. What semantic result does the currently supported Product runtime produce as a new identity?
3. Is any difference semantic, presentation-only, or unverifiable?

A stored historical semantic hash is not sufficient Frozen Path evidence. The historical Case
Replay v2 bundle must actually rebuild its Epistemic and Trust Graph projections offline.

## 2. Existing authority reused

LRD-01D composes existing contracts instead of creating a parallel engine:

- Canonical Case Ledger remains the sole writable case-history authority.
- Case Replay v2 remains the deterministic offline reconstruction contract for ledger,
  Epistemic v2, Trust Graph, runtime identity, policy and migration identity.
- `LongRangeReplayManifestV1` remains the historical long-range identity and preservation-state
  envelope.
- `ArtifactEscrowManifestV1` and `FileSystemEscrowBackendV1` remain the exact physical-byte
  verification boundary.
- the Enterprise `ProcessIsolationExecutor` remains the process/capability boundary; LRD-01D
  does not claim a kernel/container sandbox.
- `ProductRuntimeRunV1` remains the current supported Product trust-chain execution. LRD-01D
  consumes and verifies it rather than cloning Product reasoning or replay logic.

Canonical flow:

`Evidence -> CCL -> Case Replay v2 -> LRD manifest -> Escrow bytes`
`-> Frozen Path rebuild -> Current Product runtime -> DriftReportV1`

All LRD-01D outputs are immutable/content-addressed derived evidence.

## 3. Canonical semantic result

Schema: `lukart.lrd-semantic-result.v1`.

The semantic artifact contains only comparison-relevant Product semantics:

- exact case ID;
- exact reasoning target ID;
- exact deterministic reasoning-result digest;
- exact reasoning outcome;
- content-derived semantic identity.

Renderer or presentation identity is deliberately excluded. Historical semantic bytes must be
canonical JSON and their content identity must exactly equal the `SEMANTIC_RESULT` logical
identity bound in `LongRangeReplayManifestV1`.

Unknown fields, unknown outcomes, malformed digests, cross-case substitution or identity mismatch
fail closed.

## 4. Frozen Path

Schema: `lukart.lrd-frozen-path-result.v1`.

Frozen Path is offline by default and verification-only. Its fixed child worker:

1. reparses exact LRD and escrow manifests;
2. verifies exact case scope and escrow-to-LRD binding;
3. performs a deliberate network lookup probe which must be denied;
4. reads the exact escrowed `CASE_REPLAY_BUNDLE` bytes;
5. requires canonical JSON bytes and invokes existing `verify_case_replay_bundle()`;
6. thereby rebuilds Epistemic and Trust Graph identities from historical CCL bundle bytes without
   database/provider access;
7. requires the rebuilt Case Replay bundle and manifest identities to equal the identities bound
   by the historical LRD manifest;
8. reads and verifies the historical canonical semantic-result bytes;
9. derives whether historical external execution existed from the exact bound RuntimeIdentity
   provider inventory;
10. treats external outputs as verified only when exact provider request and response artifacts
    are both `PRESERVED` and present in verified escrow.

The Frozen result binds:

- exact LRD and escrow identities;
- exact rebuilt Case Replay bundle/manifest identities;
- rebuilt Epistemic, Trust Graph and RuntimeIdentity identities;
- historical canonical semantic and optional presentation identities;
- external-execution and external-output verification evidence;
- derived replay assurance;
- exact isolated task/output digests and observed capability controls.

Essential historical `CASE_REPLAY_BUNDLE` or `SEMANTIC_RESULT` material that is not `PRESERVED`
produces an explicit `UNVERIFIABLE` result with no fabricated rebuilt identity.

Assurance remains evidence-derived using the LRD-01B rules:

- complete material + deterministic rebuild + no external provider => `EXACT`;
- complete material + deterministic rebuild + external provider with exact preserved
  request/response => `VERIFIED_EXTERNAL`;
- incomplete required material => `UNVERIFIABLE`;
- preserved provider output never promotes historical provider execution to `EXACT`.

`kernel_sandbox=false` remains an explicit non-claim.

## 5. Current Path

Schema: `lukart.lrd-current-path-result.v1`.

Current Path consumes one verified `ProductRuntimeRunV1`. The existing Product runtime verifies
the current CCL-derived Epistemic projection, Trust Graph, Case Replay bundle and deterministic
ReasoningEngine result.

LRD-01D derives a fresh canonical semantic artifact from that verified run and binds it with:

- current Product runtime proof identity;
- current RuntimeIdentity digest;
- optional current presentation identity;
- content-derived Current Path identity.

The current result never overwrites, supersedes or reclassifies the historical Frozen result.
A current execution is a new derived identity even when its semantic content equals history.

## 6. Drift classification

Schema: `lukart.lrd-drift-report.v1`.

The report binds exact Frozen and Current Path identities and classifies only after case-scope and
assurance validation:

- `NO_DRIFT` — semantic identity and presentation identity both equal;
- `PRESENTATION_ONLY` — semantic identity equal, presentation identity different;
- `SEMANTIC_DRIFT` — canonical semantic identity different;
- `UNVERIFIABLE` — Frozen evidence is insufficient to establish comparison;
- `ABSTAIN` — Frozen assurance explicitly supports no comparison conclusion.

For `UNVERIFIABLE` or `ABSTAIN`, semantic/presentation equality fields are `null`; the report may
not fabricate a boolean comparison.

Cross-case Frozen/Current comparison fails closed.

## 7. Security and trust boundaries

LRD-01D grants no:

- CCL write authority;
- Gold mutation authority;
- policy/trust promotion authority;
- Product persistence authority;
- release/tag authority;
- independent-review or certification authority.

Frozen Path uses:

- fixed allow-listed worker entrypoint;
- process isolation;
- sanitized environment;
- ephemeral workspace;
- read roots limited to runtime necessities plus escrow;
- network denied under the existing Python runtime/audit boundary;
- process spawn denied;
- native FFI denied;
- CPU, memory and elapsed-time bounds inherited from `EscrowLimitsV1`.

As in 01C, this is not a claim of host firewall, network namespace, container or VM isolation.

## 8. Adversarial acceptance

The LRD-01D suite must prove at least:

- exact offline Case Replay v2 rebuild from escrowed bytes;
- rebuilt Epistemic/Trust/Runtime identities equal historical bindings;
- external-provider history derives `VERIFIED_EXTERNAL`, never `EXACT`;
- provider history without preserved exact external response becomes `UNVERIFIABLE`;
- no-provider complete deterministic history can derive `EXACT`;
- missing essential Frozen material returns explicit `UNVERIFIABLE`;
- one-byte escrow tampering fails closed;
- Case Replay logical-identity substitution fails closed;
- semantic schema/unknown-field substitution fails closed;
- current result binds a verified current Product runtime proof;
- renderer-only change is `PRESENTATION_ONLY`;
- true reasoning semantic change is `SEMANTIC_DRIFT`;
- exact semantic+presentation equality is `NO_DRIFT`;
- unverifiable history does not manufacture equality;
- cross-case substitution fails closed;
- canonical semantic identity is ordering-stable and ignores no unknown fields;
- module contains no Canonical Ledger write path.

Existing 01C path/symlink/decompression/tamper tests and Case Replay v2 migration/policy/runtime tests
remain regression dependencies rather than being weakened or duplicated.

## 9. Non-claims

LRD-01D does not claim:

- deterministic rerun of historical external providers/models;
- bit-for-bit reproduction of nondeterministic external services;
- kernel/container/VM sandboxing;
- independent 10+ year storage durability;
- cryptographic renewal completion;
- current operational-health freshness;
- independent security or archival certification;
- a new release or any change to historical `v1.0.1`.

Crypto renewal and freshness-aware operational health remain LRD-01E.

## 10. LRD-01D closure evidence

The implementation line had one fail-closed repair before the final candidate. The initial
candidate exposed nine Ruff findings in Stage Gate: one unused import plus line wrapping/import
formatting issues. The repair changed only formatting and removal of the unused import; no runtime
semantics, test expectation, threshold, security policy, trust boundary or validation gate was
weakened.

The fresh implementation candidate `6052fcb55af4dfb6cf2cd2fed76d22e8d9b0a3f6` then passed all
17 PR-triggered workflows on one unchanged exact head. The set included `LRD-01D Frozen Current
Drift`, CI Foundation, Stage Gate, Enterprise CodeQL, Enterprise Hardcore Gate, LRD-01C Artifact
Escrow Offline Runner, SSC-02, FIV-02, OPR-01, Production Validation Program and GitHub App Smoke
Test. The dedicated LRD-01D workflow completed `SUCCESS` after exact checkout, Ruff, strict MyPy,
focused/adversarial drift tests, replay/trust-chain regression and the fail-closed drift selection.
`Enterprise CodeQL` also completed `SUCCESS` on that exact head.

Guarded merge used `expected_head_sha=6052fcb55af4dfb6cf2cd2fed76d22e8d9b0a3f6` and produced
`57356225a41479274d6be00044e6c861f268a0b1`. The resulting implementation main accumulated 16
workflow runs bound to that exact SHA; all 16 were terminal `SUCCESS`, with zero queued,
in-progress or failed runs at implementation closure evaluation. The post-merge dedicated
`LRD-01D Frozen Current Drift`, `Enterprise CodeQL`, `Governance Closure PR Preparation` and
`MVROS v1 Release` guard workflows all completed `SUCCESS` on that exact main SHA.

Historical release identity remained unchanged: tag object
`9f7c0b28f766c8921e63b1d517fefcc96aa991d4` still targets
`802013c4d0e53dc12306a97e1877ebba86af64a7`, and the latest published release remains `v1.0.1`.
Repository policy continues to declare `release_enabled = false`. No release/tag publication is
authorized or performed by this closure.

This record becomes authoritative only after this exact closure candidate itself passes fresh
exact-head CI, guarded merge, resulting-main validation and baseline/release re-verification. It
records engineering evidence only and does not create Product, CCL, Gold, policy, trust-promotion,
release or independent-certification authority.

## 11. Definition of Done

LRD-01D closes only after one exact candidate SHA proves:

1. strict canonical semantic-result contract;
2. actual offline Case Replay v2 reconstruction from verified escrow bytes;
3. least-privilege Frozen Path with demonstrated network denial;
4. evidence-derived `EXACT / VERIFIED_EXTERNAL / UNVERIFIABLE` semantics;
5. verified Current Path binding to current Product runtime;
6. content-addressed semantic-vs-presentation drift report;
7. focused and adversarial tests;
8. LRD-01B/01C, Case Replay and Product Runtime regression;
9. Ruff, strict MyPy, full repository regression and security/policy gates;
10. all exact PR-head CI terminal `SUCCESS`;
11. unchanged-head guarded merge;
12. resulting-main post-merge validation terminal `SUCCESS`;
13. immutable `v1.0.1` tag/target/release baseline unchanged;
14. canonical closure evidence merged into GitHub.

## 12. Next slice

After exact LRD-01D closure, the approved continuation is:

`LRD-01E — crypto renewal / operational health`

It must add renewal attestations, storage-portability drills and freshness-aware long-range health
without rewriting historical artifact identities or inheriting stale PASS evidence from 01D.
