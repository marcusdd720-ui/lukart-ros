# LUKART ROS — Master Plan

Status: Active Post-v1 governance contract
Immutable baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Historical tag identity: `v1.0.1 tag object @ 9f7c0b28f766c8921e63b1d517fefcc96aa991d4`
Enterprise implementation base: `P3 merge @ 8550d08651957afd7f21b91553768786cb8bcf6e`
Roadmap target: `Hardcore Enterprise H1-H10`
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

Historical Enterprise contract field: Roadmap target: `Enterprise Track E0-E10`. This identifies the completed predecessor program; the active development target is the H1-H10 roadmap declared at the top of this Master Plan.

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

## 5. Active Hardcore Enterprise H1-H10

The active continuation is `docs/HARDCORE_ROADMAP.md`. It starts by closing exact-SHA/post-merge evidence and baseline-identity drift before extending repository policy enforcement, supply-chain provenance, capability isolation, replay/migration identity, tenant/case authorization, recovery, scale, auditability and final evidence closure.

A later H stage may strengthen an earlier P/E/H control but MUST NOT create a competing authority or weaken a safety invariant.

## 6. Trust boundaries

The Product epistemic authority remains the existing Evidence/Knowledge/Epistemic/Reasoning chain. Enterprise/Hardcore modules protect execution and transport around it. No infrastructure layer may create a trusted FACT, hide a contradiction, modify locked Gold or self-certify an independent review.

Agent/plugin output is untrusted until normal Product validation accepts it. External analytical `TRUSTED` state requires explicit authorization and, where trust crosses a process/API/release boundary, a verified cryptographic attestation.

## 7. Change classes

### Runtime change

Any change capable of altering Product behavior, analytical semantics, trusted state, provenance, rendering, measurement, authorization, isolation or promotion behavior. It requires focused tests, negative/adversarial tests and full regression on the exact candidate SHA.

### Evaluation change

Any change to corpora, expected results, thresholds, evaluators or certification policy. Evaluation artifacts are independently versioned and may not overwrite locked v1.0.1 evidence.

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
- `docs/HARDCORE_ROADMAP.md` — active H1-H10 continuation.

Historical design records do not override this Master Plan, Accepted ADRs, executable trust gates or the canonical working principles.
