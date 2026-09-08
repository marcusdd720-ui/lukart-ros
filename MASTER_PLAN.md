# LUKART ROS — Master Plan

Status: Active Post-v1 governance contract
Immutable baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Historical tag identity: `v1.0.1 tag object @ 9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
Enterprise implementation base: `P3 merge @ 8550d08651957afd7f21b91553768786cb8bcf6e`
Post-Hardcore closed trust core: `PHX-06 @ main 9c2a7812cedfe98b65af484186459300897357de`
Latest closed durability continuation: `DR-01 implementation merge @ main 615c01946e7ca61bb0bb5488b2a3b799eb5f06ce`
Latest closed invariant verification: `IV-01 @ main cae560f4893b8726695e06334982927376e7a146`
Latest closed signed exchange continuation: `XCH-01 @ main 83157c6e649ab1212ee200a453aa5240e08be24c`
Latest closed Product runtime convergence: `PRC-01 @ main a12cd60d2a45ce0d1807588089dbf9706cac4b22`
Latest closed Product verification evidence: `PVE-01 @ main 174b29897dcab15f7f51d5cc876aeec2b8306871`
Latest closed governance consistency: `GOV-01 implementation merge @ main 54245df8f834661c9d36a522e46952a20a095c0f`
Latest closed longitudinal KQM: `KQM-03 implementation merge @ main 85d4beaae0d0c5f736a23204cbf2103f8858f935`
Active Post-Hardcore stage: `CRY-01`
Roadmap target: `Post-Hardcore Enterprise continuation`
Development version: `1.1.0.dev0`

## 1. Immutable release baseline

The `v1.0.1` release is an immutable historical baseline. Its authoritative identity is two-level: the annotated Git tag object and the commit targeted by that tag. H1 validates both identities against repository policy and canonical documentation. Post-v1 work MUST NOT rewrite, move, reinterpret or silently replace its tag, target commit, Gold data, certification evidence or historical run outputs. Corrections after v1.0.1 are new Post-v1 changes with new SHA/evidence/provenance.

## 2. Governing principles

1. Evidence Before Conclusion.
2. Measurement Before Conclusion.
3. Validation Before Trust.
4. Factory != Product.
5. Existing cognitive components are hardened before parallel authorities are introduced.
6. Unknown/unresolved/contradictory/abstaining outcomes are first-class results.
7. Self-healing/learning/agents/plugins may propose or compute, but cannot silently change trusted epistemic state.
8. Every release/trust claim is reproducible from exact code, configuration, corpus, schema, provider and evidence identities.
9. Security boundaries are described only at the level actually enforced.
10. Missing review/security/certification evidence never becomes implicit PASS.

`docs/WORKING_PRINCIPLES.md` is the canonical living execution/trust/Hardcore standard. This Master Plan defines program structure and does not duplicate that standard.

## 3. Completed Post-v1 engineering programs

### P0/P1 — v1.1 hardening foundation

Governance, Gold candidate corpus, cognitive vertical slice, epistemic/reasoning invariants, renderer fidelity, replay/provenance, propagation/self-healing safety, KQM, failure corpus, controlled learning, performance, security/privacy, CI and operational documentation were implemented through PR #120.

### P2 — Semantic Intelligence

P2-01 through P2-10 introduced semantic regression intelligence, blast radius, cross-version replay, longitudinal quality, explainability v2, Gold candidate discovery, bounded agent runtime, digest-bound API, bounded scale/concurrency/cache and provider/plugin contracts through PR #121.

### P3 — Hardcore Hardening

P3-01 through P3-10 introduced semantic revalidation graphs, append-only replay/provenance storage, case migrations, explainability dossier integration, persistent KQM, controlled experiments, hardened agent routing, stable API v1, realistic scale primitives and plugin isolation policy through PR #122.

P0/P1/P2/P3 engineering implementation does not replace independent analytical/security review.

## 4. Enterprise Track E0-E10

E0-E10 engineering implementation was merged through PR #123 and subsequently hardened. The control set remains defined by `docs/ENTERPRISE_ROADMAP.md` and `config/enterprise_v1.json`.

Historical Enterprise contract field: Roadmap target: `Enterprise Track E0-E10`. This identifies the completed predecessor program; the active development target is the Post-Hardcore Enterprise continuation declared at the top of this Master Plan.

1. E0 Governance Reset & Release Hygiene
2. E1 Enterprise Threat Model & Trust Architecture
3. E2 Process Isolation Boundary
4. E3 Cryptographic Trust & Signed Attestations
5. E4 Software Supply Chain Security
6. E5 Identity, Authorization & Data Isolation
7. E6 Durable Provenance, Backup & Recovery
8. E7 Enterprise Observability & SRE Boundary
9. E8 Stable Enterprise API Guard
10. E9 Resilience / Chaos / Fuzz / Scale
11. E10 Enterprise Certification Gate

The automated E10 boundary remains `INDEPENDENT_REVIEW_REQUIRED` unless genuine separately attested independent review evidence exists. No repository text or automated run may manufacture that review.

## 5. Historical Hardcore Enterprise H1-H10 and Post-Hardcore continuation

`docs/HARDCORE_ROADMAP.md` is historical `CLOSED / ENGINEERING PASS`. H1-H10 closed exact-SHA/post-merge evidence and baseline-identity drift, repository-policy enforcement, supply-chain provenance, capability isolation, replay/migration identity, tenant/case authorization, recovery, scale, auditability and final evidence closure.

Post-Hardcore work MUST be defined as a separately versioned continuation. It may strengthen an earlier P/E/H control but MUST NOT reactivate H1-H10 as an active roadmap, create a competing authority or weaken a safety invariant.

The active separately versioned continuation is `docs/POST_HARDCORE_ROADMAP.md`.

PHX-01 through PHX-06 form the closed Post-Hardcore trust core. PHX-01 established the Canonical Case Ledger/Object Identity authority; PHX-02 bound immutable Gold/KQM evaluation inputs; PHX-03 made epistemic state a deterministic ledger projection; PHX-04 added the Evidence Trust Graph projection; PHX-05 closed Case Replay v2; and PHX-06 closed bounded Semantic Change Propagation v2. Detailed exact-SHA evidence and architecture contracts are recorded in `docs/POST_HARDCORE_ROADMAP.md`.

DR-01 — Canonical Ledger Recovery / Storage Portability v1 — is `CLOSED / ENGINEERING PASS` for the implementation merged through PR #157. The validated implementation head is `15312711bed0956d614de6fc3ee5005cc96f55dd`; the implementation merge is `main @ 615c01946e7ca61bb0bb5488b2a3b799eb5f06ce`. Exact-merge-SHA post-merge validation completed with nine successful workflow runs, including Stage Gate run ID `34155_634951` (underscore is a display separator for the repository PII gate). DR-01 preserves canonical case/event/bundle identities across portable restore, rejects tampered/unbound serialized metadata, refuses merge/overwrite into a non-empty target case stream and proves all-or-nothing rollback on injected mid-batch failure. It reuses the existing Canonical Case Ledger and Enterprise durability backend and does not introduce a second Product truth authority.

IV-01 — Critical Invariant Verification v1 — is `CLOSED / ENGINEERING PASS` for PR #159. The validated PR head is `fd17c13b60011afe549b8e6f68a1ca90486e98ef`; the merge is `main @ cae560f4893b8726695e06334982927376e7a146`. Its fixed content-addressed registry verifies CCL bundle integrity, recovery identity, replay rebuild, migration determinism, Epistemic rebuild and bounded semantic change by delegating to existing production contracts. The exact candidate SHA passed all 11 required PR workflows; post-merge evaluation found no failed, cancelled, queued or in-progress workflow run. IV-01 adds no CCL write or persistence authority and does not claim independent external certification.

XCH-01 — Signed Case Exchange v1 — is `CLOSED / ENGINEERING PASS` for PR #160. The validated PR head is `4da8545b4ec8584caf1a8a73aac4fc9794ba6531`; the merge is `main @ 83157c6e649ab1212ee200a453aa5240e08be24c`. XCH-01 binds an exact Case Replay v2 bundle to content-addressed exchange identity, explicit source `case:read` and recipient `case:write` authorization evidence and the existing Enterprise Ed25519 attestation contract under a dedicated domain separator. Offline verification rejects unknown schema/fields and revoked, untrusted or expired signatures. Attestation proves origin/integrity only, never epistemic truth; XCH-01 exposes no Canonical Ledger write, restore, persistence or implicit merge/import authority. The exact candidate SHA passed all 11 required PR workflows and the merge SHA completed nine post-merge workflow runs with no failed, cancelled, queued or in-progress runs when closure was evaluated.

PRC-01 — Product Runtime Convergence v1 — is `CLOSED / ENGINEERING PASS` for PR #162. The final validated PR head is `e13dabd2459c5097d7d6a720cbbfafeeb32f8b04`; the implementation merge is `main @ a12cd60d2a45ce0d1807588089dbf9706cac4b22`. PRC-01 composes the existing Canonical Case Ledger, Epistemic v2, Evidence Trust Graph, deterministic Reasoning Engine and Case Replay v2 into a content-addressed `ProductRuntimeProofV1`, while preserving the CCL as the sole writable case-history authority. Reasoning evidence must resolve to exact EVENT/ASSERTION trust nodes. The existing cognitive release guard remains the single release authorization boundary and now requires exactly one valid `product_runtime` proof binding. The final candidate passed all 11 required PR workflows; the exact implementation merge completed nine post-merge workflows, all `SUCCESS`, with no failed, cancelled, queued or in-progress run at closure evaluation. Historical `v1.0.1` tag object and target commit remained unchanged and no new release was published. No independent external certification is claimed.

PVE-01 — Product Verification Evidence v1 — is `CLOSED / ENGINEERING PASS` for PR #164. The validated PR head is `23c2ff32ba9b75ff055e8e08d50c89741494f56c`; the implementation merge is `main @ 174b29897dcab15f7f51d5cc876aeec2b8306871`. PVE-01 adds a fixed content-addressed five-check measurement registry over PRC-01 covering a supported conclusion, epistemic ABSTAIN with explicit open questions, tamper rejection, cross-case substitution rejection and evidence-identity determinism. It is measurement-only and creates no Product truth, persistence, Gold or certification authority. The exact candidate passed all 11 required PR workflows; the exact implementation merge completed nine post-merge workflow runs, all `SUCCESS`. Historical `v1.0.1` identity remained unchanged and no new release was published. No private real-case verification or independent external certification is claimed without separately available evidence.

GOV-01 — Governance Closure Consistency v1 — is `CLOSED / ENGINEERING PASS` for PR #166. The validated PR head is `07256f90282de080a19bca32d40c28fe10406ac5`; the implementation merge is `main @ 54245df8f834661c9d36a522e46952a20a095c0f`. All 11 fixed required PR workflows passed on that exact head. The resulting merge completed nine post-merge workflow runs, all `SUCCESS`, with no failed, cancelled, timed-out, queued or in-progress runs at closure evaluation. The externally observed live snapshot, canonical closure record and GOV-01 consistency report are content-addressed in `docs/GOVERNANCE_CLOSURE_CONSISTENCY_V1.md`; result `CONSISTENT` is governance-verification-only. Historical `v1.0.1` tag object and target commit remained unchanged and no new release was published. GOV-01 creates no Product truth, CCL write, release authority or independent certification claim.

KQM-03 — Identity-Preserving Longitudinal KQM v1 — is `CLOSED / ENGINEERING PASS` for PR #168. The validated PR head is `126aee3cefe10921e17beac48cd082c1fcb4bde7`; the implementation merge is `main @ 85d4beaae0d0c5f736a23204cbf2103f8858f935`. KQM-03 preserves the exact PHX-02 evaluation context, policy, evaluator and corpus identities while separately binding complete candidate runtime and exact KQM projection identity. Longitudinal comparison fails closed when evaluation input, policy, evaluator, corpus or expected metric contract changes; candidate runtime change alone remains measurable within one exact context. Persistent history reuses the existing P3 tamper-evident provenance ledger and introduces no CCL, Product, Gold or release authority. The exact candidate passed all 11 required PR workflows; the implementation merge completed nine post-merge workflow runs, all `SUCCESS`, with zero failed, cancelled, timed-out, queued or in-progress runs at closure evaluation. Historical `v1.0.1` tag object and target remained unchanged and no new release was published. No independent external certification is claimed.

The next approved stage is `CRY-01`. Its contract must be explicitly defined from current cryptographic/attestation evidence and validated under the active Post-Hardcore roadmap before implementation can be trusted or closed.

## 6. Trust boundaries

The Canonical Case Ledger is the sole authoritative writable SSOT for case history. Gold Corpus and external evidence are immutable inputs. Epistemic state, trust graphs, timelines, reasoning outputs, renderer artifacts, search indexes and later change-propagation results are deterministic/versioned projections or derived artifacts over exact ledger history; they may not become competing truth authorities.

Gold source bytes, canonical corpus content, KQM policy, evaluator/runtime identity and exact per-case Canonical Ledger heads are independently identifiable immutable inputs. `EvaluationInputIdentity` binds those inputs; `KQMProjection` is a deterministic measurement artifact only. Missing metrics fail closed, unexpected or non-finite metrics are rejected, locked evaluation is certification-only, and PHX-02 exposes no Canonical Ledger write path.

The current Gold candidate remains `candidate_pending_independent_freeze`. Repository text, automated tests, models, agents and PHX-02 code cannot manufacture an independent freeze/review claim. A real independent freeze requires separately verifiable external evidence and a separately versioned acceptance boundary.

Existing downstream components remain valid implementation assets, but authoritative state changes must be represented through the Canonical Ledger once their Post-Hardcore migration stage is active.

Enterprise/Hardcore modules protect execution, persistence and transport around Product semantics. Infrastructure layers may not create a trusted FACT, hide a contradiction, modify locked Gold or self-certify an independent review.

Agent/plugin/model output is untrusted until normal Product validation accepts it. External analytical `TRUSTED` state requires explicit authorization and, where trust crosses a process/API/release boundary, a verified cryptographic attestation. Attestation is evidence of origin/integrity, not automatic epistemic truth.

## 7. Change classes

### Runtime change

Any change capable of altering Product behavior, analytical semantics, trusted state, provenance, rendering, measurement, authorization, isolation or promotion behavior. It requires focused tests, negative/adversarial tests and full regression on the exact candidate SHA.

### Evaluation change

Any change to corpora, expected results, thresholds, evaluators or certification policy. Evaluation artifacts are independently versioned and may not overwrite locked v1.0.1 evidence. Changes to corpus content/source bytes, policy, evaluator/runtime identity, selected split or exact case ledger head produce a new evaluation identity and invalidate dependent measurements.

### Security/governance change

Any change to trust, release, workflow, permissions, supply chain, isolation or recovery contracts. Documentation alone cannot declare an unmeasured behavior PASS.

## 8. Required engineering gates

A merge candidate must pass, on one exact head SHA:

- Ruff;
- MyPy;
- focused/adversarial tests for the changed control;
- P2/P3/Enterprise compatibility tests where applicable;
- full pytest regression;
- Stage Gate;
- Enterprise/Hardcore policy and supply-chain integrity checks;
- all other repository-required status checks.

Merge MUST be SHA-bound. A moved head invalidates previous evidence. Post-merge validation MUST evaluate the resulting `main` SHA where the applicable gate supports `push`.

## 9. Certification semantics

Automated controls may establish engineering evidence. They cannot self-assert human review, external security review, penetration testing, SLSA certification, regulatory compliance or independent certification.

When automated engineering evidence is complete but required independent review is absent, the correct state is `INDEPENDENT_REVIEW_REQUIRED`.

## 10. Release governance

The package development version is distinct from the immutable historical release. Development versions MUST NOT trigger mutation/republication of an existing release tag. A stable future release requires explicit release intent, a new semantic version, exact-SHA validation evidence and a new immutable tag.

## 11. Source of detail

- `docs/WORKING_PRINCIPLES.md` — canonical living engineering standard.
- `docs/ROADMAP_V1_1.md` — P0/P1 v1.1 hardening contract.
- `docs/ROADMAP_P2.md` — P2 semantic intelligence contract.
- `docs/ROADMAP_P3.md` and `config/p3_v1.json` — P3 hardening contract/policy.
- `docs/ENTERPRISE_ROADMAP.md` and `config/enterprise_v1.json` — E0-E10 contract/policy.
- `docs/HARDCORE_ROADMAP.md` — historical H1-H10 closure contract and evidence roadmap.
- `docs/POST_HARDCORE_ROADMAP.md` — active 10+ year Post-Hardcore continuation and closure record.
- `docs/CANONICAL_CASE_LEDGER_V1.md` — PHX-01 Canonical Ledger/Object Identity v1 trust contract.
- `docs/GOLD_KQM_V2.md` — PHX-02 immutable Gold Corpus / KQM v2 trust contract.
- `docs/EPISTEMIC_ASSERTIONS_V2.md` — PHX-03 epistemic assertion/state-machine v2 trust contract.
- `docs/EVIDENCE_TRUST_GRAPH_V1.md` — PHX-04 evidence trust graph contract.
- `docs/CASE_REPLAY_V2.md` — PHX-05 deterministic case replay contract.
- `docs/SEMANTIC_CHANGE_PROPAGATION_V2.md` — PHX-06 bounded change-propagation contract.
- `docs/CRITICAL_INVARIANT_VERIFICATION_V1.md` — IV-01 bounded critical-invariant verification contract.
- `docs/SIGNED_CASE_EXCHANGE_V1.md` — XCH-01 signed offline-verifiable case exchange contract.
- `docs/PRODUCT_RUNTIME_CONVERGENCE_V1.md` — PRC-01 converged Product runtime and release-proof contract.
- `docs/PRODUCT_VERIFICATION_EVIDENCE_V1.md` — PVE-01 reproducible Product verification evidence contract.
- `docs/GOVERNANCE_CLOSURE_CONSISTENCY_V1.md` — GOV-01 governance closure consistency contract and exact live closure evidence.
- `docs/KQM_LONGITUDINAL_V1.md` — KQM-03 identity-preserving longitudinal measurement contract and exact closure evidence.

Historical design records do not override this Master Plan, Accepted ADRs, executable trust gates or the canonical working principles.