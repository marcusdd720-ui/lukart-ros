# LUKART ROS — Master Plan

Status: Active Post-v1 governance contract
Immutable baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Current engineering baseline: `P3 merge @ 8550d08651957afd7f21b91553768786cb8bcf6e`
Roadmap target: `Enterprise Track E0-E10`
Development version: `1.1.0.dev0`

## 1. Immutable release baseline

The certified `v1.0.1` release is an immutable historical baseline. Post-v1 work MUST NOT rewrite,
move, reinterpret or silently replace its tag, Gold data, certification evidence or historical run
outputs. Corrections after v1.0.1 are new Post-v1 changes with new SHA/evidence/provenance.

## 2. Governing principles

1. Evidence Before Conclusion.
2. Measurement Before Conclusion.
3. Validation Before Trust.
4. Factory != Product.
5. Existing cognitive components are hardened before parallel authorities are introduced.
6. Unknown/unresolved/contradictory/abstaining outcomes are first-class results.
7. Self-healing/learning/agents/plugins may propose or compute, but cannot silently change trusted
   epistemic state.
8. Every release/trust claim is reproducible from exact code, configuration, corpus, schema,
   provider and evidence identities.
9. Security boundaries are described only at the level actually enforced.
10. Missing review/security/certification evidence never becomes implicit PASS.

## 3. Completed Post-v1 engineering programs

### P0/P1 — v1.1 hardening foundation

Governance, Gold candidate corpus, cognitive vertical slice, epistemic/reasoning invariants,
renderer fidelity, replay/provenance, propagation/self-healing safety, KQM, failure corpus,
controlled learning, performance, security/privacy, CI and operational documentation were
implemented as Post-v1 engineering controls.

### P2 — Semantic Intelligence

P2-01 through P2-10 introduced semantic regression intelligence, blast radius, cross-version replay,
longitudinal quality, explainability v2, Gold candidate discovery, bounded agent runtime, digest-bound
API, bounded scale/concurrency/cache and provider/plugin contracts.

### P3 — Hardcore Hardening

P3-01 through P3-10 introduced semantic revalidation graphs, append-only replay/provenance storage,
case migrations, explainability dossier integration, persistent KQM, controlled experiments,
hardened agent routing, stable API v1, realistic scale primitives and plugin isolation policy.

P2/P3 engineering PASS never replaces independent analytical/security review.

## 4. Enterprise Track E0-E10

The current active program is defined by `docs/ENTERPRISE_ROADMAP.md` and
`config/enterprise_v1.json` in this exact order:

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

A later control may strengthen an earlier one but MUST NOT weaken or bypass it.

## 5. Trust boundaries

The Product epistemic authority remains the existing Evidence/Knowledge/Epistemic/Reasoning chain.
Enterprise modules protect execution and transport around it. No infrastructure layer may create a
trusted FACT, hide a contradiction, modify locked Gold or self-certify an independent review.

Agent/plugin output is untrusted until normal Product validation accepts it. External analytical
`TRUSTED` state requires explicit authorization and, where trust crosses a process/API/release
boundary, a verified cryptographic attestation.

## 6. Change classes

### Runtime change

Any change capable of altering Product behavior, analytical semantics, trusted state, provenance,
rendering, measurement, authorization, isolation or promotion behavior. It requires focused tests,
negative/adversarial tests and full regression on the exact candidate SHA.

### Evaluation change

Any change to corpora, expected results, thresholds, evaluators or certification policy. Evaluation
artifacts are independently versioned and may not overwrite locked v1.0.1 evidence.

### Security/governance change

Any change to trust, release, workflow, permissions, supply chain, isolation or recovery contracts.
Documentation alone cannot declare an unmeasured behavior PASS.

## 7. Required engineering gates

A merge candidate must pass, on one exact head SHA:

- Ruff;
- MyPy;
- focused Enterprise adversarial tests;
- P2/P3 compatibility tests;
- full pytest regression;
- Stage Gate;
- Enterprise policy/supply-chain integrity checks;
- all other repository-required status checks.

Merge MUST be SHA-bound. A moved head invalidates previous evidence.

## 8. Enterprise certification semantics

Automated Enterprise controls may produce `ENGINEERING_PASS`, `FAIL` or `INCOMPLETE`. Even when all
automated controls pass, the highest final state before real independent review is
`INDEPENDENT_REVIEW_REQUIRED`.

Terms such as externally certified, independently reviewed, penetration-tested, SLSA-certified or
regulatory-compliant MUST NOT be used unless the corresponding external evidence actually exists.

## 9. Release governance

The package development version is distinct from the immutable historical release. Development
versions MUST NOT trigger mutation/republication of an existing release tag. A stable future release
requires a new semantic version, exact-SHA validation evidence and a new immutable tag.

## 10. Source of detail

- `docs/ROADMAP_V1_1.md` — v1.1 hardening program.
- `docs/ROADMAP_P2.md` — P2 semantic intelligence.
- P3 implementation policy — `config/p3_v1.json` and P3 tests/docs.
- `docs/ENTERPRISE_ROADMAP.md` — current E0-E10 program.
- `config/enterprise_v1.json` — machine-readable Enterprise policy.

Historical documents named P3-P7 from earlier development remain historical design records and do
not override this Master Plan or the current Enterprise Track.