# LUKART ROS — Master Plan

Status: Active Post-v1 governance contract
Baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Roadmap target: `P2`

## 1. Immutable release baseline

The certified `v1.0.1` release is an immutable historical baseline. Post-v1 work starts from
its exact release SHA and must not rewrite, reinterpret, or silently replace release evidence.

Locked v1.0.1 evaluation artifacts, Gold data, certification evidence, and historical run
outputs MUST NOT be modified in order to manufacture a PASS for later code.

Any correction discovered after v1.0.1 is implemented and evaluated as a new Post-v1 change
with a new commit SHA, new evidence, and explicit provenance.

## 2. Governing principles

This plan operationalizes `FOUNDATION.md` and does not supersede accepted ADRs, safety/privacy
invariants, or `AGENTS.md`.

The Post-v1 program follows these rules:

1. Evidence Before Conclusion.
2. Measurement Before Conclusion.
3. Validation Before Trust.
4. Factory != Product.
5. Existing cognitive components are hardened and integrated before new architectural layers
   are introduced.
6. A module being present in the repository is not proof that the end-to-end Product contract
   is satisfied.
7. Unknown, unresolved, contradictory, and abstaining outcomes are first-class results.
8. Historical evidence and locked evaluation data are immutable.
9. Self-healing and learning paths may propose changes but cannot silently change trusted
   epistemic state.
10. Every release claim must be reproducible from exact code, configuration, corpus, schema,
    and evidence identities.

## 3. Post-v1 execution order

The v1.1 program is executed in this fixed order:

1. P0-01 Governance
2. P0-02 Gold Corpus v1.1
3. P0-03 Cognitive Vertical Slice
4. P0-04 Epistemic/Reasoning invariants
5. P0-05 Renderer fidelity
6. P0-06 Replay/Provenance
7. P0-07 Propagation/Self-Healing safety
8. P1-01 KQM
9. P1-02 Failure Corpus
10. P1-03 Controlled Learning
11. P1-04 Performance
12. P1-05 Security/Privacy
13. P1-06 CI architecture
14. P1-07 Documentation
15. P2 strategic development

A later stage may add implementation required by an earlier contract, but it may not weaken
or bypass an earlier gate.

## 4. Certification matrix

| Foundation requirement | Implementation authority | Required verification | Metric/evidence | Gate |
|---|---|---|---|---|
| Evidence Before Conclusion | Evidence/Knowledge + Reasoning Core | Gold + cognitive E2E + invariants | evidence coverage; unsupported conclusion rate | release |
| Explicit epistemic status | EpistemicStatusMachine | transition/invariant suite | epistemic accuracy | PR + release |
| Valid abstention | Reasoning Core | insufficient/conflicting evidence cases | abstention precision | release |
| Contradictions remain visible | Knowledge/Reasoning | contradiction cases | contradiction detection | release |
| Renderer cannot rewrite reasoning | Renderer adapters | semantic-fidelity suite | renderer fidelity | PR + release |
| Deterministic reproducibility | canonical artifacts + Replay | identical-run replay tests | replay determinism | release |
| Provenance preservation | Evidence/Reasoning/Replay | lineage + tamper tests | provenance integrity | release |
| Safe change propagation | propagation/self-healing layer | blast-radius + promotion tests | propagation correctness | release |
| Measurement independent of Product state | KQM/Gold | evaluator-isolation tests | KQM result bundle | release |
| Controlled learning only | learning candidate/promotion workflow | promotion/rollback tests | audit completeness | release |
| Privacy boundary | repository/CI/runtime contracts | synthetic-fixture + leak checks | privacy gate | PR + release |
| Exact-SHA trust | Git/CI evidence bundle | release workflow | code/config/corpus identities | release |

## 5. Change classes

### Runtime change

Any change that can alter Product behavior, analytical semantics, trusted state, provenance,
rendering, measurement, or promotion behavior. It requires applicable tests and evidence on
the exact candidate SHA.

### Evaluation change

Any change to corpora, expected results, thresholds, evaluators, or certification policy.
Evaluation changes are versioned independently and must not overwrite locked v1.0.1 data.

### Governance/documentation change

A non-runtime change defining contracts, procedures, or evidence requirements. Governance
cannot declare an unmeasured runtime behavior to be PASS.

## 6. Definition of Done for v1.1

v1.1 is eligible for certification only when:

- all P0 gates are implemented and passing;
- all P1 quality, failure, learning, performance, security/privacy, CI, and documentation
  requirements are represented by versioned artifacts;
- the Gold corpus used for release evaluation is frozen independently of candidate tuning;
- the cognitive vertical slice passes positive and negative-path evaluation;
- replay and provenance integrity are demonstrated on the exact candidate SHA;
- semantic renderer fidelity passes;
- controlled-learning/self-healing paths cannot bypass promotion governance;
- KQM release thresholds pass;
- release evidence identifies code SHA, configuration version, corpus version/hash, schemas,
  evaluators, and relevant runtime/component versions;
- no locked v1.0.1 artifact was changed to obtain the result.

## 7. Historical RC issues

Issues originating solely as pre-v1.0.1 RC review/certification gates are historical after the
certified v1.0.1 release. They may be closed as superseded/completed with an audit note; they
must not be reclassified as open v1.1 blockers unless a new Post-v1 defect is independently
reproduced and filed against a Post-v1 SHA.

## 8. Source of roadmap detail

Detailed v1.1 deliverables, acceptance criteria, and gates are maintained in
`docs/ROADMAP_V1_1.md`. P2 detail is maintained in `docs/ROADMAP_P2.md`.

## 9. P2 execution order

P2 is executed in this fixed order:

1. P2-01 Semantic Regression Intelligence
2. P2-02 Automatic Blast-Radius Analysis
3. P2-03 Cross-Version Replay & Migration Engine
4. P2-04 Longitudinal Quality Intelligence
5. P2-05 Explainability Layer v2
6. P2-06 Gold Candidate Discovery
7. P2-07 Agent Runtime v2
8. P2-08 API / Interoperability Layer
9. P2-09 Scalability / Concurrency / Caching
10. P2-10 Provider / Plugin Ecosystem

P2 adds semantic observability and bounded interoperability. It does not create a new
independent epistemic authority.

## 10. Definition of Done for P2

P2-01 through P2-10 are engineering-complete only when:

- semantic regression exposes critical meaning changes explicitly;
- blast-radius analysis deterministically identifies transitive dependents;
- cross-version replay binds equivalent inputs and detects semantic output divergence;
- longitudinal KQM trends cannot hide a regressed metric behind aggregate improvement;
- explainability is derived from actual reasoning lineage/evidence/open questions;
- failure patterns may become Gold candidates but never Gold automatically;
- agent execution is bounded, capability-routed and identity-checked;
- external API artifacts are schema/version/digest bound;
- concurrency and caching are bounded and deterministic at contract boundaries;
- plugins are versioned class registrations with duplicate/capability checks;
- focused P2 tests, full regression tests, Ruff, MyPy and Stage Gate pass on one exact SHA.

Engineering PASS for P2 does not replace Gold/KQM/human-review evidence required for future
analytical certification.
